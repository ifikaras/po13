"""CLI: python -m futures_bot --once --self-test"""

from __future__ import annotations

import argparse
import time

from futures_bot.config import load_config
from futures_bot.runner import run_cycle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Paper-trade loop for the crypto futures signal scanner. Never places live orders."
    )
    parser.add_argument("--config", default="config/futures_bot.yaml")
    parser.add_argument("--once", action="store_true", help="run a single scan cycle and exit")
    parser.add_argument("--loop", action="store_true", help="repeat scans until interrupted")
    parser.add_argument(
        "--every",
        type=int,
        default=300,
        help="seconds between scans in --loop mode (default 300)",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="ask the scanner for its offline demo data instead of a live market scan",
    )
    args = parser.parse_args(argv)

    if not args.once and not args.loop:
        parser.error("pass --once or --loop")

    config = load_config(args.config)
    self_test = True if args.self_test else None

    def cycle() -> None:
        result = run_cycle(config, self_test=self_test)
        print(
            f"approved={len(result.approved)} skipped={len(result.skipped)} "
            f"ledger={config.ledger_path}"
        )

    cycle()
    if args.once:
        return 0
    while True:
        time.sleep(max(args.every, 30))
        cycle()


if __name__ == "__main__":
    raise SystemExit(main())
