"""Paper fill / stop / take-profit accounting. No network."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from futures_bot.paper import PaperLedger


def _pos(**kwargs):
    row = {
        "ts": "2026-09-11T00:00:00Z",
        "mode": "paper",
        "status": "waiting",
        "filled": False,
        "symbol": "NEAR",
        "side": "long",
        "entry_type": "limit",
        "planned_entry": 2.54,
        "stop_loss": 2.34,
        "take_profit_1": 2.94,
        "quantity": 50.0,
        "unrealized_pnl": 0.0,
    }
    row.update(kwargs)
    return row


class MarkToMarketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "paper.json"
        self.ledger = PaperLedger(self.path, 1000.0)

    def tearDown(self):
        self.tmp.cleanup()

    def test_limit_fills_when_price_reaches_entry(self):
        self.ledger.data["positions"].append(_pos())
        events = self.ledger.mark_to_market({"NEAR": 2.54})
        pos = self.ledger.data["positions"][0]
        self.assertTrue(any("FILL NEAR" in e for e in events))
        self.assertTrue(pos["filled"])
        self.assertEqual(pos["status"], "open")
        self.assertAlmostEqual(pos["unrealized_pnl"], 0.0)

    def test_open_pnl_and_equity(self):
        self.ledger.data["positions"].append(
            _pos(status="open", filled=True, fill_price=2.54, entry_type="market")
        )
        self.ledger.mark_to_market({"NEAR": 2.64})
        pos = self.ledger.data["positions"][0]
        self.assertAlmostEqual(pos["unrealized_pnl"], 5.0)
        self.assertAlmostEqual(self.ledger.data["equity"], 1005.0)
        text = self.ledger.status_text()
        self.assertIn("starting capital: $1,000.00", text)
        self.assertIn("equity: $1,005.00", text)

    def test_stop_is_a_loss(self):
        self.ledger.data["positions"].append(
            _pos(status="open", filled=True, fill_price=2.54, entry_type="market")
        )
        events = self.ledger.mark_to_market({"NEAR": 2.30})
        pos = self.ledger.data["positions"][0]
        self.assertEqual(pos["status"], "closed")
        self.assertEqual(pos["close_reason"], "stop_loss")
        self.assertAlmostEqual(pos["realized_pnl"], (2.34 - 2.54) * 50.0)
        self.assertEqual(self.ledger.data["losses"], 1)
        self.assertTrue(any("STOP" in e for e in events))

    def test_tp1_is_a_win(self):
        self.ledger.data["positions"].append(
            _pos(status="open", filled=True, fill_price=2.54, entry_type="market")
        )
        self.ledger.mark_to_market({"NEARUSDT": 2.95})
        pos = self.ledger.data["positions"][0]
        self.assertEqual(pos["close_reason"], "take_profit_1")
        self.assertGreater(pos["realized_pnl"], 0)
        self.assertEqual(self.ledger.data["wins"], 1)
        self.assertAlmostEqual(self.ledger.data["equity"], 1000.0 + pos["realized_pnl"])


if __name__ == "__main__":
    unittest.main()
