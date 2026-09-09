"""Short-term conversation memory + optional JSON persistence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

Role = Literal["system", "user", "assistant", "tool"]

DEFAULT_MEMORY_PATH = Path("data/agent_memory.json")


@dataclass
class Message:
    role: Role
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


@dataclass
class AgentMemory:
    """Keep the last N turns; optionally mirror to a JSON file."""

    max_messages: int = 40
    path: Path = DEFAULT_MEMORY_PATH
    messages: list[Message] = field(default_factory=list)

    def add(self, message: Message) -> None:
        self.messages.append(message)
        overflow = len(self.messages) - self.max_messages
        if overflow > 0:
            # Always keep system prompt if present at index 0
            start = 1 if self.messages and self.messages[0].role == "system" else 0
            del self.messages[start : start + overflow]
        self._persist()

    def add_system(self, content: str) -> None:
        if self.messages and self.messages[0].role == "system":
            self.messages[0] = Message(role="system", content=content)
        else:
            self.messages.insert(0, Message(role="system", content=content))
        self._persist()

    def add_user(self, content: str) -> None:
        self.add(Message(role="user", content=content))

    def add_assistant(
        self,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        self.add(Message(role="assistant", content=content, tool_calls=tool_calls))

    def add_tool_result(self, tool_call_id: str, name: str, content: str) -> None:
        self.add(
            Message(
                role="tool",
                content=content,
                name=name,
                tool_call_id=tool_call_id,
            )
        )

    def as_openai_messages(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for msg in self.messages:
            item: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.name:
                item["name"] = msg.name
            if msg.tool_call_id:
                item["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                item["tool_calls"] = msg.tool_calls
            out.append(item)
        return out

    def clear_dialogue(self) -> None:
        system = self.messages[0] if self.messages and self.messages[0].role == "system" else None
        self.messages = [system] if system else []
        self._persist()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        loaded: list[Message] = []
        for row in data.get("messages", []):
            loaded.append(
                Message(
                    role=row["role"],
                    content=row.get("content") or "",
                    name=row.get("name"),
                    tool_call_id=row.get("tool_call_id"),
                    tool_calls=row.get("tool_calls"),
                )
            )
        self.messages = loaded

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"messages": [asdict(m) for m in self.messages]}
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
