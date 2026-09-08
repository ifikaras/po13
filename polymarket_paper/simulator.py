"""Virtual liquidity-rewards farming simulator using live Polymarket data."""

from __future__ import annotations

import json
import math
import random
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

USER_AGENT = "polymarket-paper-sim/1.0"
CLOB_BASE = "https://clob.polymarket.com"
GAMMA_BASE = "https://gamma-api.polymarket.com"


@dataclass
class VirtualOrder:
    side: str  # BUY or SELL
    token_id: str
    price: float
    size_usd: float
    shares: float
    spread_from_mid: float
    score_per_sample: float
    active: bool = True


@dataclass
class SimState:
    bankroll: float
    starting_bankroll: float
    rewards_earned: float = 0.0
    fill_pnl: float = 0.0
    samples: int = 0
    fills: int = 0
    market_question: str = ""
    condition_id: str = ""
    daily_pool: float = 0.0
    competitiveness: float = 0.0
    orders: list[VirtualOrder] = field(default_factory=list)
    log: list[dict[str, Any]] = field(default_factory=list)
    started_at: str = ""
    last_mid: float = 0.0


def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def score_order(max_spread: float, spread_from_mid: float, shares: float) -> float:
    """Quadratic Polymarket liquidity score for one order."""
    if max_spread <= 0 or spread_from_mid >= max_spread:
        return 0.0
    ratio = (max_spread - spread_from_mid) / max_spread
    return (ratio**2) * shares


def q_min_two_sided(q_bid: float, q_ask: float, midpoint: float) -> float:
    """Two-sided boost when midpoint is in [0.10, 0.90]."""
    if 0.10 <= midpoint <= 0.90:
        return max(min(q_bid, q_ask), max(q_bid / 3.0, q_ask / 3.0))
    return min(q_bid, q_ask)


def estimate_competition_from_book(
    token_id: str,
    mid: float,
    max_spread: float,
    fallback: float,
) -> float:
    """Rough score sum for other visible liquidity inside the reward band."""
    try:
        book = _get_json(f"{CLOB_BASE}/book?token_id={token_id}")
    except urllib.error.HTTPError:
        return fallback

    total = 0.0
    for side_rows, side in ((book.get("bids", []), "BUY"), (book.get("asks", []), "SELL")):
        for row in side_rows:
            price = float(row["price"])
            shares = float(row["size"])
            if side == "BUY":
                spread = mid - price
            else:
                spread = price - mid
            if spread <= 0 or spread >= max_spread:
                continue
            total += score_order(max_spread, spread, shares)

    return max(total, fallback)


CONSERVATIVE_SHARE = 0.10
CONSERVATIVE_FILL_DRAG_PER_DAY = 3.0


def conservative_daily_net(gross_daily: float, fill_drag: float = CONSERVATIVE_FILL_DRAG_PER_DAY) -> float:
    """Haircut model rewards and subtract fixed fill drag."""
    return gross_daily * CONSERVATIVE_SHARE - fill_drag


def pick_market(
    min_daily_rate: float = 40.0,
    max_min_size: float = 25.0,
    scan_limit: int = 60,
    order_size_usd: float | None = None,
    target_daily_net: float | None = None,
) -> dict[str, Any]:
    """
    Pick a reward market.

    Prefers larger daily pools. When order_size_usd is set, ranks by expected
    conservative daily net (10% of model share − $3 fill drag) so capital can
    aim for a target like $3–4/day.
    """
    payload = _get_json(f"{CLOB_BASE}/rewards/markets/current?limit=500")
    rows = payload.get("data", [])
    rows.sort(key=lambda r: float(r.get("total_daily_rate") or 0), reverse=True)
    candidates: list[dict[str, Any]] = []
    size = order_size_usd if order_size_usd is not None else max_min_size

    for row in rows[:scan_limit]:
        daily = float(row.get("total_daily_rate") or 0)
        min_size = float(row.get("rewards_min_size") or 999)
        if daily < min_daily_rate or min_size > size:
            continue
        cond = row["condition_id"]
        try:
            detail = _get_json(f"{CLOB_BASE}/rewards/markets/{cond}")["data"][0]
        except (urllib.error.HTTPError, KeyError, IndexError):
            time.sleep(0.08)
            continue

        tokens = detail.get("tokens") or []
        if len(tokens) < 2:
            continue
        yes = tokens[0]
        price = float(yes.get("price") or 0)
        if price <= 0.08 or price >= 0.92:
            continue

        api_comp = float(detail.get("market_competitiveness") or 0.0)
        max_spread = float(row.get("rewards_max_spread") or 0) / 100.0
        book_comp = estimate_competition_from_book(
            yes["token_id"],
            price,
            max_spread,
            fallback=max(api_comp, 15.0),
        )
        comp = max(api_comp, book_comp, 15.0)
        market = {
            "condition_id": cond,
            "question": detail.get("question", ""),
            "token_yes": yes["token_id"],
            "token_no": tokens[1]["token_id"],
            "mid": price,
            "daily_pool": daily,
            "max_spread_cents": float(row.get("rewards_max_spread") or 0),
            "min_size": min_size,
            "competitiveness": comp,
            "score_ratio": daily / comp,
        }
        _, q_you = build_orders(market, size, live_mid=False)
        gross = estimate_daily_reward(q_you, comp, daily)
        market["expected_gross_daily"] = gross
        market["expected_conservative_daily"] = conservative_daily_net(gross)
        market["q_you"] = q_you
        candidates.append(market)
        time.sleep(0.05)

    if not candidates:
        raise RuntimeError(
            "No suitable reward market found. Try a larger --order-size "
            "(unlocks higher min_size pools) or lower --min-daily-pool."
        )

    # Prefer markets that meet the daily target; otherwise highest conservative net.
    if target_daily_net is not None:
        meeting = [c for c in candidates if c["expected_conservative_daily"] >= target_daily_net]
        pool = meeting if meeting else candidates
    else:
        pool = candidates

    pool.sort(
        key=lambda x: (x["expected_conservative_daily"], x["daily_pool"], x["score_ratio"]),
        reverse=True,
    )
    return pool[0]


def size_for_daily_target(
    target_daily_net: float = 3.5,
    bankroll_buffer: float = 1.5,
    order_sizes: tuple[float, ...] = (50.0, 75.0, 100.0, 150.0, 200.0),
    min_daily_rate: float = 40.0,
    scan_limit: int = 40,
) -> dict[str, Any]:
    """
    Find the cheapest (order size, market) combo whose conservative expected
    net is >= target_daily_net. Returns sizing + chosen market.
    """
    best: dict[str, Any] | None = None
    for order_size in order_sizes:
        try:
            market = pick_market(
                min_daily_rate=min_daily_rate,
                max_min_size=order_size,
                scan_limit=scan_limit,
                order_size_usd=order_size,
                target_daily_net=target_daily_net,
            )
        except RuntimeError:
            continue
        cons = float(market["expected_conservative_daily"])
        if cons < target_daily_net:
            continue
        locked = order_size * 2
        bankroll = locked * bankroll_buffer
        candidate = {
            "order_size_usd": order_size,
            "bankroll": bankroll,
            "locked_capital": locked,
            "expected_conservative_daily": cons,
            "expected_gross_daily": market["expected_gross_daily"],
            "market": market,
        }
        if best is None or candidate["bankroll"] < best["bankroll"]:
            best = candidate
    if best is None:
        raise RuntimeError(
            f"No market/size combo reaches conservative ${target_daily_net:.2f}/day. "
            "Pools may be too competitive right now — retry later or raise order sizes."
        )
    return best


def fetch_mid(token_id: str, fallback: float) -> tuple[float, float, float]:
    """Return (mid, best_bid, best_ask) using near-mid book levels when possible."""
    book = _get_json(f"{CLOB_BASE}/book?token_id={token_id}")
    bids = [(float(b["price"]), float(b["size"])) for b in book.get("bids", [])]
    asks = [(float(a["price"]), float(a["size"])) for a in book.get("asks", [])]

    near_bids = [p for p, _ in bids if 0.05 < p < 0.95]
    near_asks = [p for p, _ in asks if 0.05 < p < 0.95]
    if near_bids and near_asks:
        best_bid = max(near_bids)
        best_ask = min(near_asks)
        return (best_bid + best_ask) / 2.0, best_bid, best_ask

    return fallback, fallback, fallback


def build_orders(
    market: dict[str, Any],
    order_size_usd: float,
    target_ratio: float = 0.5,
    live_mid: bool = True,
) -> tuple[list[VirtualOrder], float]:
    """Place virtual two-sided quotes at target_ratio * max_spread from mid."""
    max_spread = market["max_spread_cents"] / 100.0
    if live_mid:
        mid, _, _ = fetch_mid(market["token_yes"], market["mid"])
    else:
        mid = float(market["mid"])
    offset = max_spread * target_ratio

    buy_price = round(max(0.01, mid - offset), 3)
    sell_price = round(min(0.99, mid + offset), 3)

    buy_shares = order_size_usd / buy_price
    sell_shares = order_size_usd / sell_price

    buy_spread = abs(mid - buy_price)
    sell_spread = abs(sell_price - mid)

    q_bid = score_order(max_spread, buy_spread, buy_shares)
    q_ask = score_order(max_spread, sell_spread, sell_shares)
    q_total = q_min_two_sided(q_bid, q_ask, mid)

    orders = [
        VirtualOrder(
            side="BUY",
            token_id=market["token_yes"],
            price=buy_price,
            size_usd=order_size_usd,
            shares=buy_shares,
            spread_from_mid=buy_spread,
            score_per_sample=q_bid,
        ),
        VirtualOrder(
            side="SELL",
            token_id=market["token_yes"],
            price=sell_price,
            size_usd=order_size_usd,
            shares=sell_shares,
            spread_from_mid=sell_spread,
            score_per_sample=q_ask,
        ),
    ]
    return orders, q_total


def estimate_daily_reward(q_you: float, competitiveness: float, daily_pool: float) -> float:
    share = q_you / (q_you + competitiveness)
    return share * daily_pool


def maybe_fill(order: VirtualOrder, mid: float, rng: random.Random) -> float | None:
    """
    Conservative fill model: fills are usually adverse (you get picked off).
    Returns realized PnL if filled, else None.
    """
    if not order.active:
        return None

    distance = abs(order.price - mid)
    fill_prob = max(0.002, 0.05 - distance * 0.35)
    if rng.random() > fill_prob:
        return None

    order.active = False
    # Adverse move against the filled side (simplified informed flow).
    adverse = rng.uniform(0.01, 0.04)
    exit_mid = mid - adverse if order.side == "BUY" else mid + adverse
    if order.side == "BUY":
        pnl = order.shares * (exit_mid - order.price) - order.size_usd * 0.003
    else:
        pnl = order.shares * (order.price - exit_mid) - order.size_usd * 0.003

    return pnl


def run_session(
    bankroll: float = 100.0,
    order_size_usd: float = 20.0,
    samples: int = 48,
    sample_interval_sec: float = 5.0,
    seed: int = 42,
) -> SimState:
    """
    Run a live paper session.

    Each sample ~= 1 minute of epoch scoring (48 samples ~ 4 minutes live,
    extrapolated to daily in the report).
    """
    if bankroll < order_size_usd * 2:
        raise ValueError("Need at least 2x order size for two-sided virtual quotes.")

    market = pick_market(max_min_size=order_size_usd)
    orders, q_you = build_orders(market, order_size_usd)
    locked = order_size_usd * 2
    free = bankroll - locked

    state = SimState(
        bankroll=bankroll,
        starting_bankroll=bankroll,
        market_question=market["question"],
        condition_id=market["condition_id"],
        daily_pool=market["daily_pool"],
        competitiveness=market["competitiveness"],
        orders=orders,
        started_at=datetime.now(timezone.utc).isoformat(),
    )

    rng = random.Random(seed)
    daily_reward_est = estimate_daily_reward(q_you, market["competitiveness"], market["daily_pool"])
    reward_per_sample = daily_reward_est / 10_080.0

    state.log.append(
        {
            "event": "start",
            "market": market["question"],
            "daily_pool": market["daily_pool"],
            "competitiveness": market["competitiveness"],
            "q_you": round(q_you, 4),
            "estimated_daily_reward": round(daily_reward_est, 4),
            "orders": [asdict(o) for o in orders],
            "locked_capital": locked,
            "free_capital": free,
        }
    )

    for i in range(samples):
        mid, best_bid, best_ask = fetch_mid(market["token_yes"], market["mid"])
        state.last_mid = mid
        state.samples += 1
        state.rewards_earned += reward_per_sample

        fill_events: list[dict[str, Any]] = []
        for order in orders:
            pnl = maybe_fill(order, mid, rng)
            if pnl is not None:
                state.fill_pnl += pnl
                state.fills += 1
                state.bankroll += pnl
                fill_events.append({"side": order.side, "price": order.price, "pnl": round(pnl, 4)})

        state.log.append(
            {
                "event": "sample",
                "i": i + 1,
                "mid": round(mid, 4),
                "best_bid": round(best_bid, 4),
                "best_ask": round(best_ask, 4),
                "reward_accum": round(state.rewards_earned, 6),
                "fills": fill_events,
            }
        )

        if i + 1 < samples:
            time.sleep(sample_interval_sec)

    state.bankroll += state.rewards_earned
    return state


def save_report(state: SimState, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "starting_bankroll": state.starting_bankroll,
        "ending_bankroll": round(state.bankroll, 4),
        "rewards_earned": round(state.rewards_earned, 4),
        "fill_pnl": round(state.fill_pnl, 4),
        "net_pnl": round(state.bankroll - state.starting_bankroll, 4),
        "fills": state.fills,
        "samples": state.samples,
        "market_question": state.market_question,
        "condition_id": state.condition_id,
        "daily_pool": state.daily_pool,
        "competitiveness": state.competitiveness,
        "started_at": state.started_at,
        "last_mid": state.last_mid,
        "log": state.log,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def print_summary(state: SimState) -> None:
    net = state.bankroll - state.starting_bankroll
    roi = 100.0 * net / state.starting_bankroll
    extrapolated_daily = state.rewards_earned * (10_080 / max(state.samples, 1))

    print("\n=== POLYMARKET PAPER SIM — SUMMARY ===")
    print(f"Market: {state.market_question[:80]}")
    print(f"Daily reward pool: ${state.daily_pool:.2f}")
    print(f"Competitiveness (est.): {state.competitiveness:.2f}")
    print(f"Virtual bankroll: ${state.starting_bankroll:.2f} -> ${state.bankroll:.2f}")
    print(f"Rewards (this session): +${state.rewards_earned:.4f}")
    print(f"Fill P/L (this session): {state.fill_pnl:+.4f}")
    print(f"Net P/L (this session): {net:+.4f} ({roi:+.2f}%)")
    print(f"Fills during session: {state.fills} over ~{state.samples} live samples")
    print(f"Extrapolated daily rewards (model): ~${extrapolated_daily:.2f}/day")
    for label, share, fill_drag in (
        ("Optimistic", 0.50, 0.5),
        ("Base case", 0.25, 1.5),
        ("Conservative", 0.10, 3.0),
    ):
        est = extrapolated_daily * share - fill_drag
        ann = 100 * est * 365 / state.starting_bankroll
        print(f"  {label}: ~${est:+.2f}/day net (~{ann:+.0f}% annual on ${state.starting_bankroll:.0f})")
