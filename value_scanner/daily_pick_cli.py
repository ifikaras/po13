"""Print today's daily pick (for agent / automation)."""

from __future__ import annotations

import sys
from datetime import date, datetime

from value_scanner.daily_pick import evaluate_novibet_odds, find_daily_pick, parse_odds_from_text


def main() -> int:
    args = sys.argv[1:]

    if len(args) >= 2 and args[0] == "--check":
        odds = parse_odds_from_text(args[1])
        if odds is None:
            print("ERROR: invalid odds")
            return 1
        pick = find_daily_pick()
        if pick is None:
            print("ERROR: no pick found")
            return 1
        verdict = evaluate_novibet_odds(pick, odds)
        print(verdict.reason)
        print(f"Value: {verdict.value_pct:+.1f}%")
        return 0

    scan_date = date.today()
    if len(args) >= 2 and args[0] == "--date":
        scan_date = datetime.strptime(args[1], "%Y-%m-%d").date()

    pick = find_daily_pick(scan_date=scan_date)
    if pick is None:
        print("NO_PICK")
        return 1

    print("DAILY_PICK")
    print(pick.summary_greek())
    print(f"PLAY_IF_NOVIBET_ODDS>={pick.fair_odds:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
