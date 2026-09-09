"""LLM backends: OpenAI, Anthropic, or offline demo planner."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[ToolCall]
    raw: dict[str, Any] | None = None

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def detect_provider() -> str:
    """Prefer explicit AGENT_LLM, else first available API key, else demo."""
    forced = _env("AGENT_LLM").lower()
    if forced in {"openai", "anthropic", "demo"}:
        return forced
    if _env("OPENAI_API_KEY"):
        return "openai"
    if _env("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "demo"


def _http_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: int = 90) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM HTTP {exc.code}: {body[:500]}") from exc


class OpenAIClient:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or _env("OPENAI_API_KEY")
        self.model = model or _env("OPENAI_MODEL", "gpt-4o-mini")
        self.base_url = _env("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.2,
        }
        raw = _http_json(
            f"{self.base_url}/chat/completions",
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            payload,
        )
        message = raw["choices"][0]["message"]
        calls: list[ToolCall] = []
        for item in message.get("tool_calls") or []:
            fn = item.get("function") or {}
            args_raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else dict(args_raw)
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(id=item.get("id") or f"call_{len(calls)}", name=fn.get("name", ""), arguments=args))
        return LLMResponse(content=message.get("content") or "", tool_calls=calls, raw=raw)


class AnthropicClient:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or _env("ANTHROPIC_API_KEY")
        self.model = model or _env("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResponse:
        system = ""
        converted: list[dict[str, Any]] = []
        for msg in messages:
            role = msg["role"]
            if role == "system":
                system = msg.get("content") or ""
                continue
            if role == "tool":
                converted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.get("tool_call_id") or "tool",
                                "content": msg.get("content") or "",
                            }
                        ],
                    }
                )
                continue
            if role == "assistant" and msg.get("tool_calls"):
                blocks: list[dict[str, Any]] = []
                if msg.get("content"):
                    blocks.append({"type": "text", "text": msg["content"]})
                for call in msg["tool_calls"]:
                    fn = call.get("function") or {}
                    args_raw = fn.get("arguments") or "{}"
                    try:
                        args = json.loads(args_raw) if isinstance(args_raw, str) else dict(args_raw)
                    except json.JSONDecodeError:
                        args = {}
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": call.get("id") or "tool",
                            "name": fn.get("name", ""),
                            "input": args,
                        }
                    )
                converted.append({"role": "assistant", "content": blocks})
                continue
            converted.append({"role": role, "content": msg.get("content") or ""})

        anthropic_tools = []
        for tool in tools:
            fn = tool.get("function") or {}
            anthropic_tools.append(
                {
                    "name": fn.get("name"),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
                }
            )

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 2048,
            "messages": converted,
            "tools": anthropic_tools,
        }
        if system:
            payload["system"] = system

        raw = _http_json(
            "https://api.anthropic.com/v1/messages",
            {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            payload,
        )
        content_blocks = raw.get("content") or []
        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for block in content_blocks:
            if block.get("type") == "text":
                text_parts.append(block.get("text") or "")
            elif block.get("type") == "tool_use":
                calls.append(
                    ToolCall(
                        id=block.get("id") or f"call_{len(calls)}",
                        name=block.get("name") or "",
                        arguments=dict(block.get("input") or {}),
                    )
                )
        return LLMResponse(content="\n".join(text_parts).strip(), tool_calls=calls, raw=raw)


class DemoClient:
    """
    Offline planner so the heartbeat works without API keys.
    Intent routing only — not a substitute for a real LLM in production.
    """

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResponse:
        del tools  # demo uses fixed intents
        # If last messages include tool results, summarize them for the user.
        tool_results = [m for m in messages if m.get("role") == "tool"]
        if tool_results:
            last = tool_results[-1]
            name = last.get("name") or "tool"
            body = (last.get("content") or "").strip()
            preface = {
                "scan_matches": "Ορίστε το σημερινό σκαν:",
                "get_daily_pick": "Daily pick:",
                "evaluate_odds": "Αξιολόγηση απόδοσης:",
                "get_bankroll": "Καβά:",
                "place_bet": "Καταγράφηκε στοίχημα:",
                "settle_bet": "Κλείσιμο στοιχήματος:",
                "pinnacle_status": "Pinnacle status:",
            }.get(name, f"Αποτέλεσμα {name}:")
            return LLMResponse(content=f"{preface}\n\n{body}", tool_calls=[])

        user_msgs = [m for m in messages if m.get("role") == "user"]
        text = (user_msgs[-1].get("content") if user_msgs else "") or ""
        low = text.strip().lower()

        def call(name: str, **arguments: Any) -> LLMResponse:
            return LLMResponse(
                content="",
                tool_calls=[ToolCall(id=f"demo_{name}", name=name, arguments=arguments)],
            )

        if any(k in low for k in ("καβα", "καβά", "bankroll", "στοιχηματα", "στοιχήματα")):
            return call("get_bankroll")
        if any(k in low for k in ("pinnacle", "pinnapi", "sharp")):
            return call("pinnacle_status")
        if any(k in low for k in ("daily pick", "best pick", "καλύτερο", "καλυτερο")):
            return call("get_daily_pick")
        if re.search(r"#?\d+\s+.*\d+[.,]\d+", text) or re.fullmatch(r"\s*\d+[.,]\d+\s*", text):
            return call("evaluate_odds", user_text=text.strip())
        if any(k in low for k in ("σκαν", "scan", "παιχν", "ματς", "matches", "τι υπαρχει", "τι υπάρχει")):
            return call("scan_matches", force_rebuild=False)
        if "έβαλα" in low or "εβαλα" in low or "placed" in low:
            # Demo cannot invent bet fields safely — ask user / use evaluate path.
            return LLMResponse(
                content=(
                    "Για καταγραφή στοιχήματος πες: ματς, market, selection, απόδοση, stake. "
                    "Π.χ. μετά από ΠΑΙΞΕ: «βάλε 5€ στο #5 @2.03» με πραγματικό LLM."
                ),
                tool_calls=[],
            )
        # Default heartbeat action for this product: show the board
        return call("scan_matches", force_rebuild=False)


def build_llm(provider: str | None = None):
    choice = (provider or detect_provider()).lower()
    if choice == "openai":
        if not _env("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY missing")
        return OpenAIClient()
    if choice == "anthropic":
        if not _env("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY missing")
        return AnthropicClient()
    return DemoClient()
