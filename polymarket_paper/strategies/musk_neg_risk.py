"""Musk tweet neg-risk paper sim — Goldilocks + Runner-up NO signals."""

from __future__ import annotations

import json
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
    event_slug: str = ""


@dataclass
class MuskState:
    bankroll: float
    starting_bankroll: float
    positions: list[MuskPosition] = field(default_factory=list)
    cycles: int = 0
    signals: int = 0
    event_slug: str = ""
    realized_pnl: float = 0.0
    log: list[str] = field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_musk_events() -> list[dict[str, Any]]:
    """Return active Elon tweet count events, best tradeable first."""
    data = get_json(f"{GAMMA}/public-search?q=elon+musk+tweets&events_status=active")
    events = data.get("events") or []
    out: list[dict[str, Any]] = []
    for e in events:
        title = (e.get("title") or "").lower()
        if "elon musk" not in title or "tweet" not in title:
            continue
        if e.get("closed"):
            continue
        out.append(e)

    def sort_key(e: dict[str, Any]) -> tuple:
        ranked = ranked_markets(e)
        open_n = len(ranked)
        frac = life_fraction(e)
        # Prefer events with a clear mid-probability favorite (better NO payoff).
        top_yes = ranked[0][0] if ranked else 0.0
        gold_score = 1.0 - abs(top_yes - 0.28)  # sweet spot ~0.28 YES
        # Mid-life (0.25–0.85) beats brand-new or almost-done.
        life_score = 1.0 - abs(frac - 0.55)
        return (-(open_n > 0), -gold_score, -life_score, -open_n)

    out.sort(key=sort_key)
    return out


def find_musk_event() -> dict[str, Any] | None:
    events = find_musk_events()
    # Prefer an event that still has open markets and is not finished.
    for e in events:
        if ranked_markets(e):
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
    except (KeyError, ValueError, TypeError):
        return 0.5


def ranked_markets(event: dict[str, Any]) -> list[tuple[float, dict[str, Any]]]:
    rows: list[tuple[float, dict[str, Any]]] = []
    for m in event.get("markets") or []:
        if m.get("closed"):
            continue
        prices = json.loads(m.get("outcomePrices", "[]") or "[]")
        if not prices:
            continue
        yes_p = float(prices[0])
        # Skip nearly-dead / nearly-certain YES (no edge on NO).
        if yes_p <= 0.02 or yes_p >= 0.95:
            continue
        rows.append((yes_p, m))
    rows.sort(key=lambda x: x[0], reverse=True)
    return rows


def _market_no_price(market_id: str) -> tuple[float, bool]:
    """Return (no_price, is_resolved_closed)."""
    m = get_json(f"{GAMMA}/markets/{market_id}")
    prices = json.loads(m.get("outcomePrices", "[]") or "[]")
    if not prices:
        return 0.0, bool(m.get("closed"))
    no_p = float(prices[1]) if len(prices) > 1 else 1.0 - float(prices[0])
    closed = bool(m.get("closed")) or no_p >= 0.995 or no_p <= 0.005
    return no_p, closed


def settle_resolved(state: MuskState) -> int:
    """Book P/L for resolved positions into cash. Returns # settled."""
    kept: list[MuskPosition] = []
    settled = 0
    for pos in state.positions:
        try:
            no_p, closed = _market_no_price(pos.market_id)
        except Exception:
            kept.append(pos)
            continue
        if not closed:
            kept.append(pos)
            continue
        proceeds = pos.shares * no_p
        pnl = proceeds - pos.size_usd
        state.bankroll += proceeds
        state.realized_pnl += pnl
        settled += 1
        state.log.append(
            f"SETTLE {pos.signal} {pos.question[:40]} NO->{no_p:.3f} pnl={pnl:+.2f} cash=${state.bankroll:.2f}"
        )
    state.positions = kept
    return settled


def mark_positions(state: MuskState) -> tuple[float, float]:
    value = 0.0
    cost = 0.0
    for pos in state.positions:
        try:
            no_p, _ = _market_no_price(pos.market_id)
            value += pos.shares * no_p
            cost += pos.size_usd
        except Exception:
            value += pos.size_usd
            cost += pos.size_usd
    return value, value - cost


def _stake_for(state: MuskState, base_stake: float) -> float:
    """Scale stake with equity; keep dry powder for 2–4 legs."""
    pos_val, _ = mark_positions(state)
    equity = state.bankroll + pos_val
    # Aim ~20% of equity per new leg, floored/capped.
    dyn = max(base_stake, min(equity * 0.20, state.bankroll * 0.45))
    return round(min(dyn, state.bankroll), 2)


def run_cycle(
    state: MuskState,
    stake_usd: float = 15.0,
    gold_lo: float = 0.06,
    gold_hi: float = 0.55,
    min_life: float = 0.05,
    max_open: int = 6,
    events_to_trade: int = 2,
) -> MuskState:
    state.cycles += 1

    # 1) Lock in wins/losses from finished markets so cash frees up.
    settled = settle_resolved(state)

    events = find_musk_events()
    if not events:
        state.log.append(f"cycle={state.cycles} no musk events settled={settled}")
        return state

    traded_this_cycle = 0
    life_notes: list[str] = []

    for event in events[: max(events_to_trade + 2, 3)]:
        if len(state.positions) >= max_open:
            break
        ranked = ranked_markets(event)
        if not ranked:
            continue
        frac = life_fraction(event)
        life_notes.append(f"{(event.get('slug') or '')[-20:]}:{frac:.0%}")
        if frac < min_life:
            continue

        slug = event.get("slug", "")
        state.event_slug = slug
        open_ids = {p.market_id for p in state.positions}
        picks: list[tuple[str, dict[str, Any], float]] = []

        y, m = ranked[0]
        if gold_lo <= y <= gold_hi:
            picks.append(("goldilocks", m, y))
        if len(ranked) > 1:
            y2, m2 = ranked[1]
            if y2 >= 0.05:
                picks.append(("runner_up", m2, y2))
        # Third: next-most-likely bucket NO if we still have cash (more aggressive).
        if len(ranked) > 2 and state.bankroll > stake_usd:
            y3, m3 = ranked[2]
            if 0.05 <= y3 <= 0.35:
                picks.append(("third", m3, y3))

        for signal, market, yes_p in picks:
            mid = str(market.get("id", ""))
            if mid in open_ids or len(state.positions) >= max_open:
                continue
            prices = json.loads(market.get("outcomePrices", "[]") or "[]")
            no_p = float(prices[1]) if len(prices) > 1 else 1.0 - yes_p
            # Skip expensive NOs — little upside if we already paid >0.80.
            if no_p <= 0.08 or no_p >= 0.80:
                continue
            stake = _stake_for(state, stake_usd)
            if stake < 5.0 or state.bankroll < stake:
                continue

            shares = stake / no_p
            state.bankroll -= stake
            state.positions.append(
                MuskPosition(
                    market_id=mid,
                    question=(market.get("question") or "")[:80],
                    signal=signal,
                    entry_no=no_p,
                    size_usd=stake,
                    shares=shares,
                    yes_at_entry=yes_p,
                    opened_at=_now(),
                    event_slug=slug,
                )
            )
            state.signals += 1
            traded_this_cycle += 1
            open_ids.add(mid)
            state.log.append(
                f"{signal.upper()} NO @ {no_p:.3f} YES={yes_p:.3f} ${stake:.0f} | {slug[-28:]}"
            )

        if traded_this_cycle >= 2 and len([e for e in events if ranked_markets(e)]) >= 1:
            # Keep scanning a second event if we still have room/cash.
            if len(state.positions) >= max_open or state.bankroll < 5:
                break

    pos_val, unreal = mark_positions(state)
    equity = state.bankroll + pos_val
    net = equity - state.starting_bankroll
    state.log.append(
        f"cycle={state.cycles} open={len(state.positions)} cash=${state.bankroll:.2f} "
        f"equity=${equity:.2f} net={net:+.2f} unreal={unreal:+.2f} "
        f"realized={state.realized_pnl:+.2f} new={traded_this_cycle} "
        f"life={','.join(life_notes[:3]) or 'n/a'}"
    )
    return state


def state_dict(state: MuskState) -> dict[str, Any]:
    pos_val, unreal = mark_positions(state)
    equity = state.bankroll + pos_val
    return {
        "strategy": "musk_neg_risk",
        "starting_bankroll": state.starting_bankroll,
        "cash": round(state.bankroll, 2),
        "unrealized": round(unreal, 2),
        "realized_pnl": round(state.realized_pnl, 2),
        "equity": round(equity, 2),
        "net_pnl": round(equity - state.starting_bankroll, 2),
        "open_positions": len(state.positions),
        "signals": state.signals,
        "cycles": state.cycles,
        "event_slug": state.event_slug,
        "positions": [p.__dict__ for p in state.positions],
        "recent_log": state.log[-12:],
    }
