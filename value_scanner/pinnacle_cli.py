#!/usr/bin/env python3
"""Check Pinnacle (pinnapi) connection and sample sharp lines."""

from __future__ import annotations

from value_scanner.scrapers.pinnacle import (
    fetch_pinnapi_soccer_prematch,
    pinnacle_configured,
    status_report,
)


def main() -> int:
    print(status_report())
    if not pinnacle_configured():
        print("\nSetup:")
        print("1. Άνοιξε https://pinnapi.com και πάτα Generate free API key")
        print("2. Cursor → Cloud Agents → Environment → Secrets")
        print("3. Πρόσθεσε: PINNAPI_KEY = <το key σου>")
        print("4. Ξανατρέξε αυτό το agent / πες μου «δοκίμασε pinnacle»")
        return 1

    lines = fetch_pinnapi_soccer_prematch()
    print(f"\nSample ({min(5, len(lines))} of {len(lines)}):")
    for line in lines[:5]:
        ml = ""
        if line.home_win:
            ml = f"1X2 {line.home_win}/{line.draw}/{line.away_win}"
        tot = ""
        if line.over_25:
            tot = f" O/U {line.over_25}/{line.under_25}"
        print(f"  {line.league}: {line.home} vs {line.away} | {ml}{tot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
