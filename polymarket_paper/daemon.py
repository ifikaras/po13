"""24/7 paper-trading daemon for Polymarket liquidity rewards."""

from __future__ import annotations

import json
import random
import signal
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from polymarket_paper.simulator import (
    VirtualOrder,
    build_orders,
    estimate_daily_reward,
    fetch_mid,
    maybe_fill,
    pick_market,
    q_min_two_sided,
    score_order,
)

SAMPLES_PER_DAY = 10_080
CONSERVATIVE_SHARE = 0.10
CONSERVATIVE_FILL_DRAG_PER_DAY = 3.0


@dataclass
class DaemonState:
    bankroll: float
    starting_bankroll: float
    order_size_usd: float
    market: dict[str, Any] = field(default_factory=dict)
    orders: list[VirtualOrder] = field(default_factory=list)
    q_you: float = 0.0
    gross_rewards: float = 0.0
    fill_pnl: float = 0.0
    fills: int = 0
    samples: int = 0
    requotes: int = 0
    started_at: str = ""
    last_sample_at: str = ""
    last_mid: float = 0.0
    running: bool = True

    @property
    def locked_capital(self) -> float:
        return self.order_size_usd * 2

    @property
    def gross_daily_pace(self) -> float:
        if self.samples == 0:
            return 0.0
        return self.gross_rewards * (SAMPLES_PER_DAY / self.samples)

    @property
    def conservative_net_today(self) -> float:
        """Most conservative estimate: 10% pool share minus fills and daily drag."""
        gross = self.gross_rewards * CONSERVATIVE_SHARE
        hours = max(self.samples / 60.0, 0.0)
        drag = CONSERVATIVE_FILL_DRAG_PER_DAY * (hours / 24.0)
        return gross + self.fill_pnl - drag

    @property
    def ending_bankroll(self) -> float:
        return self.bankroll + self.conservative_net_today

    def to_dict(self) -> dict[str, Any]:
        return {
            "bankroll": self.bankroll,
            "starting_bankroll": self.starting_bankroll,
            "order_size_usd": self.order_size_usd,
            "market": self.market,
            "orders": [asdict(o) for o in self.orders],
            "q_you": self.q_you,
            "gross_rewards": round(self.gross_rewards, 6),
            "fill_pnl": round(self.fill_pnl, 6),
            "fills": self.fills,
            "samples": self.samples,
            "requotes": self.requotes,
            "started_at": self.started_at,
            "last_sample_at": self.last_sample_at,
            "last_mid": self.last_mid,
            "conservative_net_today": round(self.conservative_net_today, 4),
            "gross_daily_pace": round(self.gross_daily_pace, 4),
            "ending_bankroll_conservative": round(self.ending_bankroll, 4),
        }


def load_state(path: Path) -> DaemonState | None:
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    orders = [VirtualOrder(**o) for o in raw.get("orders", [])]
    st = DaemonState(
        bankroll=raw["bankroll"],
        starting_bankroll=raw["starting_bankroll"],
        order_size_usd=raw["order_size_usd"],
        market=raw.get("market", {}),
        orders=orders,
        q_you=raw.get("q_you", 0.0),
        gross_rewards=raw.get("gross_rewards", 0.0),
        fill_pnl=raw.get("fill_pnl", 0.0),
        fills=raw.get("fills", 0),
        samples=raw.get("samples", 0),
        requotes=raw.get("requotes", 0),
        started_at=raw.get("started_at", ""),
        last_sample_at=raw.get("last_sample_at", ""),
        last_mid=raw.get("last_mid", 0.0),
    )
    return st


def save_state(state: DaemonState, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def append_log(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")


def utc_day_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def needs_requote(state: DaemonState, mid: float) -> bool:
    if not state.orders:
        return True
    max_spread = state.market["max_spread_cents"] / 100.0
    threshold = max_spread * 0.25
    for order in state.orders:
        if not order.active:
            continue
        if abs(mid - order.price) > max_spread * 0.6:
            return True
        ideal_offset = max_spread * 0.5
        if order.side == "BUY":
            target = mid - ideal_offset
        else:
            target = mid + ideal_offset
        if abs(order.price - target) > threshold:
            return True
    return False


def requote(state: DaemonState, mid: float) -> None:
    orders, q_you = build_orders(state.market, state.order_size_usd, target_ratio=0.5)
    state.orders = orders
    state.q_you = q_you
    state.requotes += 1
    state.last_mid = mid


def init_daemon(bankroll: float, order_size_usd: float) -> DaemonState:
    market = pick_market(max_min_size=order_size_usd)
    orders, q_you = build_orders(market, order_size_usd)
    now = datetime.now(timezone.utc).isoformat()
    return DaemonState(
        bankroll=bankroll,
        starting_bankroll=bankroll,
        order_size_usd=order_size_usd,
        market=market,
        orders=orders,
        q_you=q_you,
        started_at=now,
        last_sample_at=now,
    )


def run_daemon(
    bankroll: float = 100.0,
    order_size_usd: float = 20.0,
    sample_interval_sec: float = 60.0,
    state_path: Path = Path("data/polymarket_paper_state.json"),
    log_path: Path = Path("data/polymarket_paper_daily.log"),
    seed: int = 42,
    stop_at_utc_midnight: bool = True,
) -> DaemonState:
    if bankroll < order_size_usd * 2:
        raise ValueError("Need at least 2x order size for two-sided quotes.")

    day_started = utc_day_key()
    state = load_state(state_path)
    if state is None or not state.market:
        append_log(log_path, "Scanning reward markets (top pools by daily rate)...")
        state = init_daemon(bankroll, order_size_usd)
        append_log(
            log_path,
            f"START market={state.market['question'][:60]} pool=${state.market['daily_pool']:.0f}/d "
            f"bankroll=${bankroll:.0f} order=${order_size_usd:.0f}/side",
        )
    else:
        append_log(log_path, f"RESUME samples={state.samples} conservative_net=${state.conservative_net_today:.2f}")

    rng = random.Random(seed + state.samples)
    daily_reward_est = estimate_daily_reward(
        state.q_you, state.market["competitiveness"], state.market["daily_pool"]
    )
    reward_per_sample = daily_reward_est / SAMPLES_PER_DAY
    last_hour_log = -1

    def _stop(_signum: int, _frame: object) -> None:
        state.running = False
        append_log(log_path, "STOP signal received")

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    while state.running:
        if stop_at_utc_midnight and utc_day_key() != day_started:
            append_log(log_path, "UTC midnight reached — stopping for day rollover")
            break

        token = state.market["token_yes"]
        mid, best_bid, best_ask = fetch_mid(token, state.market["mid"])
        state.market["mid"] = mid
        state.last_mid = mid
        state.samples += 1
        state.last_sample_at = datetime.now(timezone.utc).isoformat()

        if needs_requote(state, mid):
            requote(state, mid)
            daily_reward_est = estimate_daily_reward(
                state.q_you, state.market["competitiveness"], state.market["daily_pool"]
            )
            reward_per_sample = daily_reward_est / SAMPLES_PER_DAY
            append_log(
                log_path,
                f"REQUOTE mid={mid:.3f} buy={state.orders[0].price:.3f} sell={state.orders[1].price:.3f}",
            )

        state.gross_rewards += reward_per_sample

        for order in state.orders:
            pnl = maybe_fill(order, mid, rng)
            if pnl is not None:
                state.fill_pnl += pnl
                state.fills += 1
                append_log(
                    log_path,
                    f"FILL {order.side} @ {order.price:.3f} pnl={pnl:+.2f} mid={mid:.3f}",
                )
                # Replace filled side after adverse fill
                requote(state, mid)
                daily_reward_est = estimate_daily_reward(
                    state.q_you, state.market["competitiveness"], state.market["daily_pool"]
                )
                reward_per_sample = daily_reward_est / SAMPLES_PER_DAY

        save_state(state, state_path)

        hour = datetime.now(timezone.utc).hour
        if hour != last_hour_log and state.samples % 60 == 0:
            last_hour_log = hour
            append_log(
                log_path,
                (
                    f"HOURLY samples={state.samples} mid={mid:.3f} "
                    f"gross=${state.gross_rewards:.3f} fills={state.fills} "
                    f"fill_pnl={state.fill_pnl:+.2f} "
                    f"conservative_net=${state.conservative_net_today:+.2f} "
                    f"pace=${state.gross_daily_pace:.2f}/d gross"
                ),
            )
            print(
                f"[{state.last_sample_at[:19]}] conservative net today: "
                f"${state.conservative_net_today:+.2f} | fills={state.fills} | samples={state.samples}"
            )

        time.sleep(sample_interval_sec)

    save_state(state, state_path)
    append_log(
        log_path,
        (
            f"DONE samples={state.samples} gross_rewards=${state.gross_rewards:.3f} "
            f"fill_pnl={state.fill_pnl:+.2f} conservative_net=${state.conservative_net_today:+.2f}"
        ),
    )
    return state


def print_daemon_summary(state: DaemonState) -> None:
    hours = state.samples / 60.0
    print("\n=== POLYMARKET PAPER DAEMON — DAY SUMMARY ===")
    print(f"Market: {state.market.get('question', '')[:80]}")
    print(f"Runtime: ~{hours:.1f}h ({state.samples} samples @ 1/min)")
    print(f"Virtual bankroll start: ${state.starting_bankroll:.2f}")
    print(f"Gross rewards (model): +${state.gross_rewards:.4f}")
    print(f"Fill P/L: {state.fill_pnl:+.4f} ({state.fills} fills, {state.requotes} requotes)")
    print(f"Gross daily pace: ~${state.gross_daily_pace:.2f}/day")
    print(f"\n--- CONSERVATIVE (10% share, $3/day fill drag) ---")
    print(f"Net today (so far): ${state.conservative_net_today:+.2f}")
    print(f"Bankroll (conservative): ${state.ending_bankroll:.2f}")
    print(f"ROI today: {100 * state.conservative_net_today / state.starting_bankroll:+.2f}%")
    if hours > 0.5:
        proj = state.conservative_net_today * (24.0 / hours)
        print(f"Projected full-day conservative net: ~${proj:+.2f}")
    else:
        print("Projected full-day: wait until ~30+ minutes of samples for reliable projection")
