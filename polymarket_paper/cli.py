#!/usr/bin/env python3
"""CLI for Polymarket liquidity-rewards paper simulator."""

from __future__ import annotations

import argparse
from pathlib import Path

from polymarket_paper.daemon import print_daemon_summary, run_daemon
from polymarket_paper.multi_runner import print_all_status, run_multi
from polymarket_paper.simulator import print_summary, run_session, save_report, size_for_daily_target


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
    bankroll = args.bankroll
    order_size = args.order_size
    if args.target_daily and bankroll is None and order_size is None:
        print(
            f"Auto-sizing for conservative ~${args.target_daily:.2f}/day "
            f"(pools ≥ ${args.min_daily_pool:.0f}/d)..."
        )
    else:
        print(
            f"Starting 24/7 paper daemon: bankroll=${bankroll or 'auto'}, "
            f"order=${order_size or 'auto'}/side, interval={args.interval}s"
        )
    print(f"State: {args.state} | Log: {args.log}")
    print("Conservative tracking: 10% of model rewards, $3/day fill drag")
    if args.reset:
        print("RESET: discarding previous state and retargeting market")
    print("Press Ctrl+C or send SIGTERM to stop gracefully.\n")

    state = run_daemon(
        bankroll=bankroll,
        order_size_usd=order_size,
        sample_interval_sec=args.interval,
        state_path=args.state,
        log_path=args.log,
        seed=args.seed,
        stop_at_utc_midnight=not args.no_midnight_stop,
        reset=args.reset,
        target_daily_net=args.target_daily,
        min_daily_rate=args.min_daily_pool,
    )
    print_daemon_summary(state)


def cmd_size(args: argparse.Namespace) -> None:
    print(
        f"Scanning live reward markets for conservative ≥ ${args.target_daily:.2f}/day "
        f"(pools ≥ ${args.min_daily_pool:.0f}/d)..."
    )
    sizing = size_for_daily_target(
        target_daily_net=args.target_daily,
        min_daily_rate=args.min_daily_pool,
    )
    m = sizing["market"]
    print("\n=== SIZING RESULT ===")
    print(f"Market: {m['question'][:80]}")
    print(f"Daily pool: ${m['daily_pool']:.0f}")
    print(f"Order size: ${sizing['order_size_usd']:.0f}/side")
    print(f"Locked capital: ${sizing['locked_capital']:.0f}")
    print(f"Recommended bankroll (1.5x buffer): ${sizing['bankroll']:.0f}")
    print(f"Expected model gross: ${sizing['expected_gross_daily']:+.2f}/day")
    print(f"Expected conservative net: ${sizing['expected_conservative_daily']:+.2f}/day")
    print(
        "\nStart with:\n"
        f"  python3 -m polymarket_paper.cli daemon --reset "
        f"--bankroll {sizing['bankroll']:.0f} --order-size {sizing['order_size_usd']:.0f} "
        f"--target-daily {args.target_daily}"
    )


def cmd_multi(args: argparse.Namespace) -> None:
    only = args.only  # None => all strategies
    label = ",".join(only) if only else "weather,mirror,musk"
    print(
        f"Starting paper sim: strategies={label} "
        f"bankroll=${args.bankroll:.0f}, interval={args.interval}s"
    )
    run_multi(
        bankroll=args.bankroll,
        interval_sec=args.interval,
        data_dir=args.data_dir,
        log_path=args.log,
        once=args.once,
        only=only,
    )


def cmd_multi_status(args: argparse.Namespace) -> None:
    print_all_status(args.data_dir, only=args.only)


def cmd_status(args: argparse.Namespace) -> None:
    """Default status is the live Musk paper bot."""
    print_all_status(Path("data/strategies"), only=["musk"])


def cmd_lp_status(args: argparse.Namespace) -> None:
    from polymarket_paper.daemon import load_state

    state = load_state(args.state)
    if state is None:
        print("No LP daemon state found (LP is stopped).")
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
    p_daemon.add_argument(
        "--bankroll",
        type=float,
        default=None,
        help="Virtual bankroll (default: auto-size for --target-daily)",
    )
    p_daemon.add_argument(
        "--order-size",
        type=float,
        default=None,
        help="USD per side (default: auto-size for --target-daily)",
    )
    p_daemon.add_argument(
        "--target-daily",
        type=float,
        default=3.5,
        help="Conservative net $/day target used for market pick + auto-size (default 3.5)",
    )
    p_daemon.add_argument(
        "--min-daily-pool",
        type=float,
        default=40.0,
        help="Ignore reward markets with daily pool below this",
    )
    p_daemon.add_argument("--interval", type=float, default=60.0, help="Seconds between samples (60=1/min)")
    p_daemon.add_argument("--seed", type=int, default=42)
    p_daemon.add_argument("--state", type=Path, default=Path("data/polymarket_paper_state.json"))
    p_daemon.add_argument("--log", type=Path, default=Path("data/polymarket_paper_daily.log"))
    p_daemon.add_argument("--no-midnight-stop", action="store_true", help="Keep running past UTC midnight")
    p_daemon.add_argument("--reset", action="store_true", help="Clear state and retarget market/capital")
    p_daemon.set_defaults(func=cmd_daemon)

    p_size = sub.add_parser("size", help="Show capital needed for a conservative $/day target")
    p_size.add_argument("--target-daily", type=float, default=3.5)
    p_size.add_argument("--min-daily-pool", type=float, default=40.0)
    p_size.set_defaults(func=cmd_size)

    p_status = sub.add_parser("status", help="Show Musk paper bot status (only live strategy)")
    p_status.set_defaults(func=cmd_status)

    p_lp = sub.add_parser("lp-status", help="Show LP daemon state")
    p_lp.add_argument("--state", type=Path, default=Path("data/polymarket_paper_state.json"))
    p_lp.set_defaults(func=cmd_lp_status)

    p_multi = sub.add_parser("multi", help="Run paper strategies (default: musk only)")
    p_multi.add_argument("--bankroll", type=float, default=33.33, help="Virtual capital (used only if no saved state)")
    p_multi.add_argument("--interval", type=float, default=300.0, help="Seconds between cycles (default 5min)")
    p_multi.add_argument("--once", action="store_true", help="Run one cycle and exit")
    p_multi.add_argument(
        "--only",
        nargs="+",
        default=["musk"],
        help="Which strategies to run (default: musk). Options: musk weather mirror",
    )
    p_multi.add_argument("--data-dir", type=Path, default=Path("data/strategies"))
    p_multi.add_argument("--log", type=Path, default=Path("data/strategies_daily.log"))
    p_multi.set_defaults(func=cmd_multi)

    p_ms = sub.add_parser("multi-status", help="Status for strategy paper bots")
    p_ms.add_argument("--data-dir", type=Path, default=Path("data/strategies"))
    p_ms.add_argument("--only", nargs="+", default=None)
    p_ms.set_defaults(func=cmd_multi_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
