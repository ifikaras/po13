"""Run multiple paper strategy simulators in one daemon loop."""

from __future__ import annotations

import json
import signal
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from polymarket_paper.strategies.musk_neg_risk import MuskState, run_cycle as musk_cycle, state_dict as musk_dict
from polymarket_paper.strategies.wallet_mirror import MirrorState, run_cycle as mirror_cycle, state_dict as mirror_dict
from polymarket_paper.strategies.weather_edge import WeatherState, run_cycle as weather_cycle, state_dict as weather_dict

STRATEGIES = {
    "weather": (WeatherState, weather_cycle, weather_dict),
    "mirror": (MirrorState, mirror_cycle, mirror_dict),
    "musk": (MuskState, musk_cycle, musk_dict),
}


def _load(path: Path, cls: type, bankroll: float) -> Any:
    if not path.exists():
        return cls(bankroll=bankroll, starting_bankroll=bankroll)
    raw = json.loads(path.read_text(encoding="utf-8"))
    st = cls(bankroll=raw.get("bankroll", bankroll), starting_bankroll=raw.get("starting_bankroll", bankroll))
    if cls is WeatherState:
        from polymarket_paper.strategies.weather_edge import PaperPosition

        st.positions = [PaperPosition(**p) for p in raw.get("positions", [])]
        st.cycles = raw.get("cycles", 0)
        st.signals = raw.get("signals", 0)
        st.log = raw.get("log", [])
    elif cls is MirrorState:
        from polymarket_paper.strategies.wallet_mirror import MirrorPosition

        st.positions = [MirrorPosition(**p) for p in raw.get("positions", [])]
        st.seen_keys = set(raw.get("seen_keys", []))
        st.cycles = raw.get("cycles", 0)
        st.copies = raw.get("copies", 0)
        st.log = raw.get("log", [])
    elif cls is MuskState:
        from polymarket_paper.strategies.musk_neg_risk import MuskPosition

        st.positions = [MuskPosition(**p) for p in raw.get("positions", [])]
        st.cycles = raw.get("cycles", 0)
        st.signals = raw.get("signals", 0)
        st.event_slug = raw.get("event_slug", "")
        st.log = raw.get("log", [])
    return st


def _save(path: Path, st: Any, dict_fn: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict_fn(st)
    payload["bankroll"] = st.bankroll
    payload["starting_bankroll"] = st.starting_bankroll
    if hasattr(st, "seen_keys"):
        payload["seen_keys"] = list(st.seen_keys)
    if hasattr(st, "positions"):
        payload["positions"] = [asdict(p) for p in st.positions]
    if hasattr(st, "log"):
        payload["log"] = st.log[-50:]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _selected(only: list[str] | None) -> dict[str, Any]:
    if not only:
        names = list(STRATEGIES)
    else:
        names = []
        for name in only:
            key = name.strip().lower()
            if key in ("musk_neg_risk", "musk-neg-risk"):
                key = "musk"
            if key in ("weather_edge", "weather-edge"):
                key = "weather"
            if key in ("wallet_mirror", "wallet-mirror"):
                key = "mirror"
            if key not in STRATEGIES:
                raise ValueError(f"Unknown strategy {name!r}. Choose from: {', '.join(STRATEGIES)}")
            names.append(key)
    return {name: STRATEGIES[name] for name in names}


def run_multi(
    bankroll: float = 100.0,
    interval_sec: float = 300.0,
    data_dir: Path = Path("data/strategies"),
    log_path: Path = Path("data/strategies_daily.log"),
    once: bool = False,
    only: list[str] | None = None,
) -> None:
    selected = _selected(only)
    n = max(len(selected), 1)
    states = {}
    for name, (cls, _, dict_fn) in selected.items():
        per = bankroll / n
        path = data_dir / f"{name}_state.json"
        states[name] = (path, cls, _load(path, cls, per), dict_fn)

    running = True

    def _stop(_a: int, _b: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    with log_path.open("a", encoding="utf-8") as logf:
        logf.write(
            f"\n[{datetime.now(timezone.utc).isoformat()}] MULTI START "
            f"bankroll={bankroll} only={','.join(states)}\n"
        )

        while running:
            summary_parts = []
            for name, (path, cls, st, dict_fn) in states.items():
                try:
                    _, cycle_fn, _ = selected[name]
                    st = cycle_fn(st)
                    _save(path, st, dict_fn)
                    states[name] = (path, cls, st, dict_fn)
                    d = dict_fn(st)
                    summary_parts.append(f"{name}: ${d['net_pnl']:+.2f} ({d.get('open_positions',0)} pos)")
                    for line in d.get("recent_log", [])[-2:]:
                        logf.write(f"  [{name}] {line}\n")
                except Exception as exc:
                    logf.write(f"  [{name}] ERROR {exc}\n")
                    summary_parts.append(f"{name}: ERR")

            line = f"[{datetime.now(timezone.utc).strftime('%H:%M')}] " + " | ".join(summary_parts)
            logf.write(line + "\n")
            logf.flush()
            print(line)
            if once:
                break
            time.sleep(interval_sec)


def print_all_status(
    data_dir: Path = Path("data/strategies"),
    only: list[str] | None = None,
) -> None:
    selected = _selected(only)
    title = "MUSK PAPER STATUS" if list(selected) == ["musk"] else "MULTI STRATEGY PAPER STATUS"
    print(f"\n=== {title} ===")
    total_start = 0.0
    total_equity = 0.0
    for name in selected:
        path = data_dir / f"{name}_state.json"
        if not path.exists():
            print(f"\n{name}: not started")
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        total_start += raw.get("starting_bankroll", 0)
        total_equity += raw.get("equity", raw.get("starting_bankroll", 0))
        print(f"\n--- {raw.get('strategy', name)} ---")
        for k in ("equity", "net_pnl", "cash", "unrealized", "open_positions", "cycles"):
            if k in raw:
                print(f"  {k}: {raw[k]}")
        for line in raw.get("recent_log", [])[-5:]:
            print(f"  > {line}")
    print(f"\nTOTAL: ${total_start:.2f} -> ${total_equity:.2f} (net ${total_equity - total_start:+.2f})")
