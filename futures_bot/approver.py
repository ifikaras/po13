"""Deterministic approval rules on top of a scanner setup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from futures_bot.config import ApprovalSettings, RiskSettings


CONVICTION_RANK = {
    "weak": 0,
    "low": 0,
    "moderate": 1,
    "medium": 1,
    "strong": 2,
    "high": 2,
}


@dataclass(frozen=True)
class Decision:
    approved: bool
    reasons: tuple[str, ...]
    entry_type: str  # market | limit
    planned_entry: float | None
    quantity: float | None
    notional: float | None
    risk_cash: float | None

    @property
    def summary(self) -> str:
        verb = "APPROVE" if self.approved else "SKIP"
        return f"{verb}: " + "; ".join(self.reasons)


def _num(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _conviction_rank(label: str | None) -> int:
    if not label:
        return -1
    text = str(label).strip().lower()
    for key, rank in CONVICTION_RANK.items():
        if key in text:
            return rank
    return -1


def size_position(
    entry: float,
    stop_loss: float,
    account_size: float,
    risk_pct: float,
) -> tuple[float, float, float] | None:
    """Return (qty, notional, risk_cash) so a stop hit loses ~risk_pct of account."""
    stop_dist = abs(entry - stop_loss)
    if stop_dist <= 0 or entry <= 0 or account_size <= 0 or risk_pct <= 0:
        return None
    risk_cash = account_size * (risk_pct / 100.0)
    qty = risk_cash / stop_dist
    return qty, qty * entry, risk_cash


def decide(
    row: dict[str, Any],
    approval: ApprovalSettings,
    risk: RiskSettings,
    *,
    open_symbols: set[str],
    open_count: int,
    daily_new: int,
) -> Decision:
    reasons: list[str] = []
    symbol = str(row.get("symbol") or "").upper()
    if not symbol:
        return Decision(False, ("missing symbol",), "market", None, None, None, None)

    if symbol in open_symbols:
        return Decision(False, (f"{symbol} already has an open paper position",), "market", None, None, None, None)
    if open_count >= risk.max_open_positions:
        return Decision(
            False,
            (f"max open positions reached ({risk.max_open_positions})",),
            "market",
            None,
            None,
            None,
            None,
        )
    if daily_new >= risk.max_daily_new_positions:
        return Decision(
            False,
            (f"max daily new positions reached ({risk.max_daily_new_positions})",),
            "market",
            None,
            None,
            None,
            None,
        )

    if approval.require_hard_filters and row.get("passes_hard_filters") is False:
        extra = row.get("hard_filter_reasons") or []
        detail = " ".join(str(x) for x in extra) if extra else "failed hard filters"
        reasons.append(detail)

    score = _num(row, "total_score")
    if score is None:
        score = _num(row, "score")
    if score is None or score < approval.min_score:
        reasons.append(f"score {score} below min {approval.min_score}")

    conv_rank = _conviction_rank(row.get("conviction") or row.get("strength"))
    need_rank = _conviction_rank(approval.min_conviction)
    if conv_rank < need_rank:
        reasons.append(
            f"conviction {row.get('conviction') or row.get('strength')!r} below {approval.min_conviction}"
        )

    market_entry = _num(row, "entry")
    optimal_entry = _num(row, "optimal_entry")
    stop_loss = _num(row, "stop_loss")
    tp1 = _num(row, "take_profit_1")
    if market_entry is None or stop_loss is None or tp1 is None:
        reasons.append("missing entry/stop/tp1")
        return Decision(False, tuple(reasons), "market", None, None, None, None)
    if stop_loss >= market_entry:
        reasons.append("stop loss is not below entry (long-only)")

    planned_entry = market_entry
    entry_type = "market"
    if optimal_entry is not None and optimal_entry < market_entry:
        discount_pct = (market_entry - optimal_entry) / market_entry * 100.0
        if discount_pct > approval.max_chase_pct:
            planned_entry = optimal_entry
            entry_type = "limit"
            reasons.append(
                f"wait for pullback: market {market_entry:.6g} is {discount_pct:.2f}% above optimal {optimal_entry:.6g}"
            )
        else:
            reasons.append(f"chase allowed ({discount_pct:.2f}% above optimal)")

    rr1 = _num(row, "optimal_risk_reward_1") if entry_type == "limit" else _num(row, "risk_reward_1")
    if entry_type == "limit" and rr1 is None:
        rr1 = _num(row, "risk_reward_1")
    if rr1 is None or rr1 < approval.min_optimal_rr1:
        reasons.append(f"R:R {rr1} below min {approval.min_optimal_rr1}")

    if approval.require_leverage_safe and risk.intended_leverage:
        if row.get("leverage_safe") is False:
            reasons.append(f"unsafe at {risk.intended_leverage}x (would likely liquidate before stop)")

    if approval.require_confirmation and not row.get("confirmation_checked"):
        reasons.append("confirmation layer was not checked")

    sized = size_position(planned_entry, stop_loss, risk.account_size, risk.risk_pct)
    if sized is None:
        reasons.append("could not size position (bad entry/stop or risk settings)")
        return Decision(False, tuple(reasons), entry_type, planned_entry, None, None, None)
    qty, notional, risk_cash = sized

    if reasons and not all(
        r.startswith("wait for pullback") or r.startswith("chase allowed") for r in reasons
    ):
        # Keep informational entry notes only on approvals; any real skip reason rejects.
        skip_reasons = [
            r
            for r in reasons
            if not r.startswith("wait for pullback") and not r.startswith("chase allowed")
        ]
        if skip_reasons:
            return Decision(False, tuple(skip_reasons), entry_type, planned_entry, qty, notional, risk_cash)

    info = [r for r in reasons if r.startswith("wait for pullback") or r.startswith("chase allowed")]
    info.append(
        f"{symbol} {entry_type} qty={qty:.6g} @ {planned_entry:.6g} SL={stop_loss:.6g} "
        f"TP1={tp1:.6g} risk=${risk_cash:.2f}"
    )
    return Decision(True, tuple(info), entry_type, planned_entry, qty, notional, risk_cash)
