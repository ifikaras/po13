#!/usr/bin/env python3
"""CLI for Polymarket liquidity-rewards paper simulator."""

from __future__ import annotations

import argparse
from pathlib import Path

from polymarket_paper.simulator import print_summary, run_session, save_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Polymarket liquidity rewards paper simulator")
    parser.add_argument("--bankroll", type=float, default=100.0, help="Virtual starting capital (USD)")
    parser.add_argument("--order-size", type=float, default=20.0, help="USD per side (two-sided)")
    parser.add_argument("--samples", type=int, default=36, help="Live price samples to collect")
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds between samples")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for fill simulation")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("data/polymarket_paper_report.json"),
        help="Where to write JSON report",
    )
    args = parser.parse_args()

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


if __name__ == "__main__":
    main()
