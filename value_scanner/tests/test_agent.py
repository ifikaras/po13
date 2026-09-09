"""Tests for the first-agent heartbeat (demo provider, no API keys)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from value_scanner.agent.llm import DemoClient, detect_provider
from value_scanner.agent.loop import Agent
from value_scanner.agent.memory import AgentMemory
from value_scanner.agent.tools import execute_tool, tool_get_bankroll


class MemoryTests(unittest.TestCase):
    def test_persists_and_trims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mem.json"
            mem = AgentMemory(max_messages=5, path=path)
            mem.add_system("sys")
            for i in range(10):
                mem.add_user(f"u{i}")
            self.assertEqual(mem.messages[0].role, "system")
            self.assertLessEqual(len(mem.messages), 5)
            mem2 = AgentMemory(path=path)
            mem2.load()
            self.assertEqual(mem2.messages[0].content, "sys")


class DemoPlannerTests(unittest.TestCase):
    def test_bankroll_intent(self) -> None:
        client = DemoClient()
        resp = client.complete(
            [{"role": "user", "content": "καβά"}],
            tools=[],
        )
        self.assertTrue(resp.wants_tools)
        self.assertEqual(resp.tool_calls[0].name, "get_bankroll")

    def test_odds_intent(self) -> None:
        client = DemoClient()
        resp = client.complete(
            [{"role": "user", "content": "#5 2.03"}],
            tools=[],
        )
        self.assertEqual(resp.tool_calls[0].name, "evaluate_odds")

    def test_summarizes_tool_result(self) -> None:
        client = DemoClient()
        resp = client.complete(
            [
                {"role": "user", "content": "καβά"},
                {
                    "role": "tool",
                    "name": "get_bankroll",
                    "tool_call_id": "x",
                    "content": "Διαθέσιμα μετρητά: €100",
                },
            ],
            tools=[],
        )
        self.assertFalse(resp.wants_tools)
        self.assertIn("€100", resp.content)


class ToolTests(unittest.TestCase):
    def test_unknown_tool(self) -> None:
        raw = execute_tool("nope", {})
        data = json.loads(raw)
        self.assertEqual(data["error"], "unknown_tool")

    def test_bankroll_tool(self) -> None:
        text = tool_get_bankroll()
        self.assertIn("μετρητά", text.lower())


class AgentLoopTests(unittest.TestCase):
    def test_heartbeat_bankroll(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mem = AgentMemory(path=Path(tmp) / "m.json")
            agent = Agent(provider="demo", memory=mem, persist_memory=False)
            result = agent.run("καβά")
            self.assertEqual(result.provider, "demo")
            self.assertGreaterEqual(len(result.tool_trace), 1)
            self.assertEqual(result.tool_trace[0]["tool"], "get_bankroll")
            self.assertIn("μετρητά", result.reply.lower())

    def test_evaluate_odds_with_board_stub(self) -> None:
        from value_scanner.scan_board import ScanCandidate

        fake_board = [
            ScanCandidate(
                index=5,
                sport="football",
                home="Alpha",
                away="Beta",
                league="Test League",
                kickoff_utc="2099-01-01T18:00:00Z",
                status="ΕΠΟΜΕΝΟ",
                market="BTTS",
                selection="No",
                model_probability=55.0,
                fair_odds=1.82,
                expected_goals="1.1-1.0",
                novibet_path="BTTS → Όχι",
            )
        ]

        with tempfile.TemporaryDirectory() as tmp:
            mem = AgentMemory(path=Path(tmp) / "m.json")
            agent = Agent(provider="demo", memory=mem, persist_memory=False)
            with (
                patch("value_scanner.agent.tools.get_or_build_today_board", return_value=fake_board),
                patch(
                    "value_scanner.agent.tools.evaluate_novibet_odds",
                    return_value=type(
                        "V",
                        (),
                        {
                            "should_play": True,
                            "reason": "ΠΑΙΞΕ — anchored edge ok",
                            "value_pct": 4.5,
                            "anchor_note": "test",
                        },
                    )(),
                ),
            ):
                result = agent.run("#5 2.03")
            self.assertEqual(result.tool_trace[0]["tool"], "evaluate_odds")
            self.assertIn("ΠΑΙΞΕ", result.reply)

    def test_detect_provider_demo_by_default(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            # Keep PATH-like env empty of API keys
            self.assertEqual(detect_provider(), "demo")


if __name__ == "__main__":
    raise SystemExit(unittest.main())
