"""Approval-rule unit tests. No network."""

from __future__ import annotations

import unittest

from futures_bot.approver import decide
from futures_bot.config import ApprovalSettings, RiskSettings

DEMO = {
    "symbol": "DEMOUP",
    "name": "Demo Uptrend Coin",
    "conviction": "Moderate",
    "total_score": 6.0,
    "score": 6.0,
    "entry": 152.08814197242793,
    "optimal_entry": 148.24064399410418,
    "stop_loss": 142.36759429455267,
    "take_profit_1": 163.57965495235004,
    "take_profit_2": 170.47456274030333,
    "risk_reward_1": 1.18,
    "optimal_risk_reward_1": 2.61,
    "passes_hard_filters": True,
    "futures_available": False,
}


def _decide(row=None, approval=None, risk=None, open_symbols=None, open_count=0, daily_new=0):
    return decide(
        dict(DEMO if row is None else row),
        approval or ApprovalSettings(),
        risk or RiskSettings(),
        open_symbols=open_symbols or set(),
        open_count=open_count,
        daily_new=daily_new,
    )


class ApproverTests(unittest.TestCase):
    def test_demo_approves_limit_on_pullback(self):
        d = _decide()
        self.assertTrue(d.approved, d.summary)
        self.assertEqual(d.entry_type, "limit")
        self.assertAlmostEqual(d.planned_entry, DEMO["optimal_entry"])
        self.assertGreater(d.quantity, 0)
        self.assertAlmostEqual(d.risk_cash, 10.0)  # 1% of 1000

    def test_small_discount_is_market_chase(self):
        # Market R:R on the demo is 1.18, so relax the floor to isolate entry-type.
        d = _decide(approval=ApprovalSettings(max_chase_pct=5.0, min_optimal_rr1=1.0))
        self.assertTrue(d.approved, d.summary)
        self.assertEqual(d.entry_type, "market")
        self.assertAlmostEqual(d.planned_entry, DEMO["entry"])

    def test_low_score_skipped(self):
        row = dict(DEMO, total_score=3.0, score=3.0)
        d = _decide(row=row)
        self.assertFalse(d.approved)
        self.assertTrue(any("score" in r for r in d.reasons))

    def test_already_open_skipped(self):
        d = _decide(open_symbols={"DEMOUP"})
        self.assertFalse(d.approved)
        self.assertTrue(any("already has an open" in r for r in d.reasons))

    def test_max_open_positions(self):
        d = _decide(open_count=3, risk=RiskSettings(max_open_positions=3))
        self.assertFalse(d.approved)
        self.assertTrue(any("max open" in r for r in d.reasons))

    def test_hard_filters(self):
        row = dict(DEMO, passes_hard_filters=False, hard_filter_reasons=["below EMA200"])
        d = _decide(row=row)
        self.assertFalse(d.approved)
        self.assertTrue(any("EMA200" in r for r in d.reasons))

    def test_unsafe_leverage(self):
        row = dict(DEMO, leverage_safe=False)
        d = _decide(row=row)
        self.assertFalse(d.approved)
        self.assertTrue(any("unsafe" in r for r in d.reasons))

    def test_weak_rr_on_limit(self):
        row = dict(DEMO, optimal_risk_reward_1=1.1, risk_reward_1=0.8)
        d = _decide(row=row)
        self.assertFalse(d.approved)
        self.assertTrue(any("R:R" in r for r in d.reasons))

    def test_strong_conviction_required(self):
        d = _decide(approval=ApprovalSettings(min_conviction="strong"))
        self.assertFalse(d.approved)
        self.assertTrue(any("conviction" in r for r in d.reasons))


if __name__ == "__main__":
    unittest.main()
