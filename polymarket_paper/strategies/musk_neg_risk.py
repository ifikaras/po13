"""Musk tweet neg-risk paper sim — Goldilocks + Runner-up NO signals."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from polymarket_paper.http_util import get_json

GAMMA = "https://gamma-api.polymarket.com"


@dataclass
class MuskPosition:
    market_id: str
    question: str
    signal: str
    entry_no: float
    size_usd: float
    shares: float
    yes_at_entry: float
    opened_at: str


@dataclass
class MuskState:
    bankroll: float
    starting_bankroll: float
    positions: list[MuskPosition] = field(default_factory=list)
    cycles: int = 0
    signals: int = 0
    event_slug: str = ""
    log: list[str] = field(default_factory=list)


def find_musk_event() -> dict[str, Any] | None:
    data = get_json(f"{GAMMA}/public-search?q=elon+musk+tweets&events_status=active")
    events = data.get("events") or []
    for e in events:
        if "elon musk" in (e.get("title") or "").lower() and "tweet" in (e.get("title") or "").lower():
            return e
    return events[0] if events else None


def life_fraction(event: dict[str, Any]) -> float:
    try:
        start = datetime.fromisoformat(event["startDate"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(event["endDate"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        total = (end - start).total_seconds()
        if total <= 0:
            return 1.0
        return max(0.0, min(1.0, (now - start).total_seconds() / total))
    except (KeyError, ValueError):
        return 0.5


def ranked_markets(event: dict[str, Any]) -> list[tuple[float, dict[str, Any]]]:
    import json

    rows: list[tuple[float, dict[str, Any]]] = []
    for m in event.get("markets") or []:
        if m.get("closed"):
            continue
        prices = json.loads(m.get("outcomePrices", "[]") or "[]")
        if not prices:
            continue
        yes_p = float(prices[0])
        rows.append((yes_p, m))
    rows.sort(key=lambda x: x[0], reverse=True)
    return rows


def mark_positions(state: MuskState) -> tuple[float, float]:
    import json

    value = 0.0
    cost = 0.0
    for pos in state.positions:
        try:
            m = get_json(f"{GAMMA}/markets/{pos.market_id}")
            prices = json.loads(m.get("outcomePrices", "[]") or "[]")
            no_p = float(prices[1]) if len(prices) > 1 else 1.0 - float(prices[0])
            value += pos.shares * no_p
            cost += pos.size_usd
        except Exception:
            value += pos.size_usd
            cost += pos.size_usd
    return value, value - cost


def run_cycle(
    state: MuskState,
    stake_usd: float = 12.0,
    gold_lo: float = 0.08,
    gold_hi: float = 0.42,
    min_life: float = 0.30,
) -> MuskState:
    state.cycles += 1
    event = find_musk_event()
    if not event:
        state.log.append("no musk event found")
        return state

    state.event_slug = event.get("slug", "")
    frac = life_fraction(event)
    if frac < min_life:
        state.log.append(f"life_frac={frac:.2f} too early")
        return state

    ranked = ranked_markets(event)
    open_ids = {p.market_id for p in state.positions}
    picks: list[tuple[str, dict[str, Any], float]] = []

    if ranked:
        y, m = ranked[0]
        if gold_lo <= y <= gold_hi:
            picks.append(("goldilocks", m, y))
    if len(ranked) > 1:
        y2, m2 = ranked[1]
        if y2 >= 0.05:
            picks.append(("runner_up", m2, y2))

    import json

    for signal, market, yes_p in picks:
        mid = str(market.get("id", ""))
        if mid in open_ids or len(state.positions) >= 4:
            continue
        prices = json.loads(market.get("outcomePrices", "[]") or "[]")
        no_p = float(prices[1]) if len(prices) > 1 else 1.0 - yes_p
        if no_p <= 0.02 or no_p >= 0.98:
            continue
        if state.bankroll < stake_usd:
            continue

        shares = stake_usd / no_p
        state.bankroll -= stake_usd
        state.positions.append(
            MuskPosition(
                market_id=mid,
                question=(market.get("question") or "")[:80],
                signal=signal,
                entry_no=no_p,
                size_usd=stake_usd,
                shares=shares,
                yes_at_entry=yes_p,
                opened_at=datetime.now(timezone.utc).isoformat(),
            )
        )
        state.signals += 1
        open_ids.add(mid)
        state.log.append(f"{signal.upper()} NO @ {no_p:.3f} (YES was {yes_p:.3f})")

    pos_val, unreal = mark_positions(state)
    state.log.append(f"cycle={state.cycles} life={frac:.0%} open={len(state.positions)} unreal={unreal:+.2f}")
    return state


def state_dict(state: MuskState) -> dict[str, Any]:
    pos_val, unreal = mark_positions(state)
    equity = state.bankroll + pos_val
    return {
        "strategy": "musk_neg_risk",
        "starting_bankroll": state.starting_bankroll,
        "cash": round(state.bankroll, 2),
        "unrealized": round(unreal, 2),
        "equity": round(equity, 2),
        "net_pnl": round(equity - state.starting_bankroll, 2),
        "open_positions": len(state.positions),
        "signals": state.signals,
        "cycles": state.cycles,
        "event_slug": state.event_slug,
        "positions": [p.__dict__ for p in state.positions],
        "recent_log": state.log[-10:],
    }
