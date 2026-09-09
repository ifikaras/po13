"""Agent heartbeat: model → tool → result → model."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from value_scanner.agent.llm import LLMResponse, ToolCall, build_llm, detect_provider
from value_scanner.agent.memory import AgentMemory
from value_scanner.agent.tools import TOOL_SPECS, execute_tool

SYSTEM_PROMPT = """Είσαι ο Novibet Value Agent — ένας μικρός, συγκεκριμένος AI agent.

Αποστολή (μία μόνο): βοήθησε τον χρήστη να βρει και να αξιολογήσει value bets στη Novibet.

Ροή εργασίας:
1. Σκάνισε αγώνες (scan_matches) και δείξε αριθμημένη λίστα.
2. Ο χρήστης στέλνει αποδόσεις Novibet: «#5 BTTS Όχι 2.03».
3. Κάλεσε evaluate_odds και απάντησε ΠΑΙΞΕ ή SKIP (+ value / stake hint αν υπάρχει).
4. Αν ρωτήσει «καβά», κάλεσε get_bankroll.
5. Μην χτίζεις «universal agent». Μην προσθέτεις άσχετα features.

Κανόνες:
- Μίλα Ελληνικά, σύντομα και καθαρά.
- Χρησιμοποίησε tools για πραγματικά δεδομένα — μην εφευρίσκεις αποδόσεις ή αγώνες.
- Αν λείπουν στοιχεία για place_bet / settle_bet, ρώτα πριν καλέσεις το tool.
- Κράτα το scope μικρό: ένα συγκεκριμένο job, end-to-end.
"""


@dataclass
class TurnResult:
    reply: str
    steps: int
    tool_trace: list[dict[str, Any]]
    provider: str


class Agent:
    def __init__(
        self,
        provider: str | None = None,
        memory: AgentMemory | None = None,
        max_steps: int = 8,
        persist_memory: bool = True,
    ) -> None:
        self.provider = provider or detect_provider()
        self.llm = build_llm(self.provider)
        self.memory = memory or AgentMemory()
        if persist_memory:
            self.memory.load()
        if not self.memory.messages or self.memory.messages[0].role != "system":
            self.memory.add_system(SYSTEM_PROMPT)
        else:
            self.memory.add_system(SYSTEM_PROMPT)
        self.max_steps = max_steps

    def run(self, user_text: str) -> TurnResult:
        self.memory.add_user(user_text)
        trace: list[dict[str, Any]] = []

        for step in range(1, self.max_steps + 1):
            response = self.llm.complete(self.memory.as_openai_messages(), TOOL_SPECS)
            if response.wants_tools:
                self._record_assistant_with_tools(response)
                for call in response.tool_calls:
                    result = execute_tool(call.name, call.arguments)
                    self.memory.add_tool_result(call.id, call.name, result)
                    trace.append(
                        {
                            "step": step,
                            "tool": call.name,
                            "arguments": call.arguments,
                            "result_preview": result[:400],
                        }
                    )
                continue

            reply = (response.content or "").strip() or "(κενή απάντηση μοντέλου)"
            self.memory.add_assistant(reply)
            return TurnResult(reply=reply, steps=step, tool_trace=trace, provider=self.provider)

        fallback = "Έφτασα το όριο βημάτων χωρίς τελική απάντηση. Δοκίμασε ξανά με πιο συγκεκριμένο αίτημα."
        self.memory.add_assistant(fallback)
        return TurnResult(reply=fallback, steps=self.max_steps, tool_trace=trace, provider=self.provider)

    def _record_assistant_with_tools(self, response: LLMResponse) -> None:
        openai_calls = []
        for call in response.tool_calls:
            openai_calls.append(
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments, ensure_ascii=False),
                    },
                }
            )
        self.memory.add_assistant(response.content or "", tool_calls=openai_calls)


def run_agent_once(user_text: str, provider: str | None = None, persist_memory: bool = False) -> TurnResult:
    agent = Agent(provider=provider, persist_memory=persist_memory)
    if not persist_memory:
        agent.memory.clear_dialogue()
        agent.memory.add_system(SYSTEM_PROMPT)
    return agent.run(user_text)
