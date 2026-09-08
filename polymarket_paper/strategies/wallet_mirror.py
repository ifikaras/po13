"""Wallet mirror paper sim — copy recent trades from top leaderboard wallets."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from polymarket_paper.http_util import get_json

DATA_API = "https://data-api.polymarket.com"
GAMMA = "https://gamma-api.polymarket.com"


@dataclass
class MirrorPosition:
    condition_id: str
    title: str
    outcome: str
    side: str
    entry_price: float
    size_usd: float
    shares: float
    copied_from: str
    opened_at: str


@dataclass
class MirrorState:
    bankroll: float
    starting_bankroll: float
    positions: list[MirrorPosition] = field(default_factory=list)
    closed_pnl: float = 0.0
    seen_keys: set[str] = field(default_factory=set)
    cycles: int = 0
    copies: int = 0
    log: list[str] = field(default_factory=list)


def fetch_leaderboard(limit: int = 15) -> list[dict[str, Any]]:
    rows = get_json(f"{DATA_API}/v1/leaderboard?timePeriod=MONTH&orderBy=PNL&limit={limit}")
    return rows if isinstance(rows, list) else []


def fetch_activity(wallet: str, limit: int = 20) -> list[dict[str, Any]]:
    rows = get_json(f"{DATA_API}/activity?user={wallet}&limit={limit}")
    return rows if isinstance(rows, list) else []


def mark_positions(state: MirrorState) -> tuple[float, float]:
    value = 0.0
    cost = 0.0
    for pos in state.positions:
        try:
            markets = get_json(f"{GAMMA}/markets?condition_ids={pos.condition_id}")
            if not markets:
                continue
            m = markets[0]
            import json

            outcomes = json.loads(m.get("outcomes", "[]"))
            prices = json.loads(m.get("outcomePrices", "[]"))
            idx = outcomes.index(pos.outcome) if pos.outcome in outcomes else 0
            px = float(prices[idx]) if idx < len(prices) else 0.0
            value += pos.shares * px
            cost += pos.size_usd
        except Exception:
            value += pos.size_usd
            cost += pos.size_usd
    return value, value - cost


def run_cycle(state: MirrorState, stake_usd: float = 10.0, max_positions: int = 8) -> MirrorState:
    state.cycles += 1
    open_keys = {f"{p.condition_id}:{p.outcome}" for p in state.positions}

    for row in fetch_leaderboard(12):
        wallet = row.get("proxyWallet", "")
        user = row.get("userName") or wallet[:10]
        pnl = float(row.get("pnl") or 0)
        vol = float(row.get("vol") or 0)
        if not wallet or pnl <= 5000 or vol <= 0:
            continue

        for act in fetch_activity(wallet, 15):
            if act.get("type") != "TRADE":
                continue
            key = act.get("transactionHash") or f"{act.get('timestamp')}:{act.get('asset')}"
            if key in state.seen_keys:
                continue
            state.seen_keys.add(key)

            side = act.get("side", "BUY")
            if side != "BUY":
                continue

            cond = act.get("conditionId") or ""
            outcome = act.get("outcome") or ""
            pos_key = f"{cond}:{outcome}"
            if pos_key in open_keys or len(state.positions) >= max_positions:
                continue

            price = float(act.get("price") or 0)
            if price <= 0.05 or price >= 0.95:
                continue
            if state.bankroll < stake_usd:
                continue

            slip = min(price * 1.03, 0.99)
            shares = stake_usd / slip
            state.bankroll -= stake_usd
            state.positions.append(
                MirrorPosition(
                    condition_id=cond,
                    title=(act.get("title") or "")[:70],
                    outcome=outcome,
                    side="BUY",
                    entry_price=slip,
                    size_usd=stake_usd,
                    shares=shares,
                    copied_from=user,
                    opened_at=datetime.now(timezone.utc).isoformat(),
                )
            )
            state.copies += 1
            open_keys.add(pos_key)
            state.log.append(f"COPY {user} BUY {outcome[:20]} @ {slip:.3f} | {act.get('title','')[:40]}")

    pos_val, unreal = mark_positions(state)
    state.log.append(f"cycle={state.cycles} open={len(state.positions)} copies={state.copies} unreal={unreal:+.2f}")
    return state


def state_dict(state: MirrorState) -> dict[str, Any]:
    pos_val, unreal = mark_positions(state)
    equity = state.bankroll + pos_val
    return {
        "strategy": "wallet_mirror",
        "starting_bankroll": state.starting_bankroll,
        "cash": round(state.bankroll, 2),
        "unrealized": round(unreal, 2),
        "equity": round(equity, 2),
        "net_pnl": round(equity - state.starting_bankroll, 2),
        "open_positions": len(state.positions),
        "copies": state.copies,
        "cycles": state.cycles,
        "positions": [p.__dict__ for p in state.positions[-8:]],
        "recent_log": state.log[-10:],
    }
