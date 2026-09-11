"""CLI: python -m futures_bot --once --reset-ledger --skip-confirmation"""

from __future__ import annotations

import argparse
import time

from futures_bot.config import load_config
from futures_bot.paper import PaperLedger
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
    parser.add_argument(
        "--reset-ledger",
        action="store_true",
        help="wipe paper positions before this run (drops DEMOUP / old virtual trades)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="only scan the first N symbols (faster smoke run)",
    )
    parser.add_argument(
        "--skip-confirmation",
        action="store_true",
        help="TA-only scan (skip StockTwits/Reddit/OI confirmation) so a virtual run finishes sooner",
    )
    parser.add_argument(
        "--skip-social",
        action="store_true",
        help="skip StockTwits + Reddit only; keep other confirmation layers",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="print open paper positions and exit (no scan)",
    )
    args = parser.parse_args(argv)

    if not args.once and not args.loop and not args.status:
        parser.error("pass --once, --loop, or --status")

    config = load_config(args.config).with_scan_overrides(
        limit=args.limit,
        skip_confirmation=args.skip_confirmation,
        skip_social=args.skip_social,
        self_test=args.self_test,
    )

    if args.reset_ledger:
        PaperLedger(config.ledger_path, config.risk.account_size).reset()
        print(f"reset paper ledger {config.ledger_path}")

    if args.status:
        ledger = PaperLedger(config.ledger_path, config.risk.account_size)
        print(ledger.status_text())
        return 0

    def cycle() -> None:
        result = run_cycle(config, self_test=True if args.self_test else None)
        print(
            f"approved={len(result.approved)} skipped={len(result.skipped)} "
            f"setups={result.setups} scanned={result.scanned} "
            f"ledger={config.ledger_path}"
        )
        ledger = PaperLedger(config.ledger_path, config.risk.account_size)
        print(ledger.status_text())

    cycle()
    if args.once:
        return 0
    while True:
        time.sleep(max(args.every, 30))
        cycle()


if __name__ == "__main__":
    raise SystemExit(main())
