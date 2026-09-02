#!/usr/bin/env python3
"""CLI for Polymarket liquidity-rewards paper simulator."""

from __future__ import annotations

import argparse
from pathlib import Path

from polymarket_paper.daemon import print_daemon_summary, run_daemon
from polymarket_paper.multi_runner import print_all_status, run_multi
from polymarket_paper.simulator import print_summary, run_session, save_report


def cmd_session(args: argparse.Namespace) -> None:
    print(
        f"Starting paper sim: bankroll=${args.bankroll:.2f}, "
        f"order=${args.order_size:.2f}/side, samples={args.samples}, interval={args.interval}s"
    )
    state = run_session(
        bankroll=args.bankroll,
        order_size_usd=args.order_size,
        samples=args.samples,
        sample_interval_sec=args.interval,
        seed=args.seed,
    )
    save_report(state, args.report)
    print_summary(state)
    print(f"\nFull report: {args.report}")


def cmd_daemon(args: argparse.Namespace) -> None:
    print(
        f"Starting 24/7 paper daemon: bankroll=${args.bankroll:.2f}, "
        f"order=${args.order_size:.2f}/side, interval={args.interval}s"
    )
    print(f"State: {args.state} | Log: {args.log}")
    print("Conservative tracking: 10% pool share, $3/day fill drag")
    print("Press Ctrl+C or send SIGTERM to stop gracefully.\n")

    state = run_daemon(
        bankroll=args.bankroll,
        order_size_usd=args.order_size,
        sample_interval_sec=args.interval,
        state_path=args.state,
        log_path=args.log,
        seed=args.seed,
        stop_at_utc_midnight=not args.no_midnight_stop,
    )
    print_daemon_summary(state)


def cmd_multi(args: argparse.Namespace) -> None:
    print(
        f"Starting multi-strategy paper sim: ${args.bankroll:.0f} total "
        f"(${args.bankroll/3:.1f}/strategy), interval={args.interval}s"
    )
    print("Strategies: weather_edge | wallet_mirror | musk_neg_risk")
    run_multi(
        bankroll=args.bankroll,
        interval_sec=args.interval,
        data_dir=args.data_dir,
        log_path=args.log,
        once=args.once,
    )


def cmd_multi_status(args: argparse.Namespace) -> None:
    print_all_status(args.data_dir)


def cmd_status(args: argparse.Namespace) -> None:
    from polymarket_paper.daemon import load_state

    state = load_state(args.state)
    if state is None:
        print("No daemon state found. Start with: python3 -m polymarket_paper.cli daemon")
        return
    print_daemon_summary(state)


def main() -> None:
    parser = argparse.ArgumentParser(description="Polymarket liquidity rewards paper simulator")
    sub = parser.add_subparsers(dest="command", required=True)

    p_session = sub.add_parser("session", help="Short live paper session")
    p_session.add_argument("--bankroll", type=float, default=100.0)
    p_session.add_argument("--order-size", type=float, default=20.0)
    p_session.add_argument("--samples", type=int, default=36)
    p_session.add_argument("--interval", type=float, default=5.0)
    p_session.add_argument("--seed", type=int, default=42)
    p_session.add_argument("--report", type=Path, default=Path("data/polymarket_paper_report.json"))
    p_session.set_defaults(func=cmd_session)

    p_daemon = sub.add_parser("daemon", help="Run all day until UTC midnight (or stop signal)")
    p_daemon.add_argument("--bankroll", type=float, default=100.0)
    p_daemon.add_argument("--order-size", type=float, default=20.0)
    p_daemon.add_argument("--interval", type=float, default=60.0, help="Seconds between samples (60=1/min)")
    p_daemon.add_argument("--seed", type=int, default=42)
    p_daemon.add_argument("--state", type=Path, default=Path("data/polymarket_paper_state.json"))
    p_daemon.add_argument("--log", type=Path, default=Path("data/polymarket_paper_daily.log"))
    p_daemon.add_argument("--no-midnight-stop", action="store_true", help="Keep running past UTC midnight")
    p_daemon.set_defaults(func=cmd_daemon)

    p_status = sub.add_parser("status", help="Show current daemon state")
    p_status.add_argument("--state", type=Path, default=Path("data/polymarket_paper_state.json"))
    p_status.set_defaults(func=cmd_status)

    p_multi = sub.add_parser("multi", help="Run weather + wallet mirror + musk paper sims")
    p_multi.add_argument("--bankroll", type=float, default=100.0, help="Total virtual capital split /3")
    p_multi.add_argument("--interval", type=float, default=300.0, help="Seconds between cycles (default 5min)")
    p_multi.add_argument("--once", action="store_true", help="Run one cycle and exit")
    p_multi.add_argument("--data-dir", type=Path, default=Path("data/strategies"))
    p_multi.add_argument("--log", type=Path, default=Path("data/strategies_daily.log"))
    p_multi.set_defaults(func=cmd_multi)

    p_ms = sub.add_parser("multi-status", help="Status for all 3 strategy sims")
    p_ms.add_argument("--data-dir", type=Path, default=Path("data/strategies"))
    p_ms.set_defaults(func=cmd_multi_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
