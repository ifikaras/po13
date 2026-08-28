#!/usr/bin/env python3
"""CLI for daily value bet scanning."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

import yaml

from value_scanner.scanner import ScanConfig, pick_best_daily_bet, scan


def _load_manual_odds(path: Path | None) -> dict[str, dict]:
    if path is None or not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    return data.get("matches", {})


def _print_fixture(result, show_all: bool = False) -> None:
    fixture = result.fixture
    probs = result.probabilities
    print(f"\n{'=' * 72}")
    print(f"{fixture.league} | {fixture.home_name} vs {fixture.away_name}")
    print(f"Kickoff UTC: {fixture.kickoff_utc}")
    print(
        f"Form (home venue): {fixture.home_name} {fixture.home_form.scored:.2f} GF / "
        f"{fixture.home_form.conceded:.2f} GA ({fixture.home_form.matches_used} matches)"
    )
    print(
        f"Form (away venue): {fixture.away_name} {fixture.away_form.scored:.2f} GF / "
        f"{fixture.away_form.conceded:.2f} GA ({fixture.away_form.matches_used} matches)"
    )
    print(
        f"Expected goals: {probs.lambda_home:.2f} - {probs.lambda_away:.2f} | "
        f"Over 2.5: {probs.over_25 * 100:.1f}% | BTTS: {probs.btts_yes * 100:.1f}% | "
        f"1X2: {probs.home_win * 100:.1f}% / {probs.draw * 100:.1f}% / {probs.away_win * 100:.1f}%"
    )
    print(f"Odds source: {result.odds_source}")

    if result.value_bets:
        print("\nVALUE BETS:")
        for bet in result.value_bets:
            print(
                f"  • {bet.market} / {bet.selection} @ {bet.odds} | "
                f"model {bet.model_probability}% vs implied {bet.implied_probability}% | "
                f"value +{bet.value_pct}% | fair odds {bet.fair_odds}"
            )
    elif show_all:
        print("\nFair odds in target range (1.70-1.85) — χρειάζονται αποδόσεις bookmaker:")
        for market in result.fair_markets:
            if market["in_target_range"]:
                print(
                    f"  • {market['market']} / {market['selection']} | "
                    f"model {market['probability_pct']}% | fair odds {market['fair_odds']}"
                )


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily value bet scanner (FotMob + Poisson model)")
    parser.add_argument("--date", help="Scan date YYYY-MM-DD (default: today)")
    parser.add_argument("--min-odds", type=float, default=1.70)
    parser.add_argument("--max-odds", type=float, default=1.85)
    parser.add_argument("--min-value", type=float, default=3.0, help="Minimum value %%")
    parser.add_argument("--days", type=int, default=1, help="Days ahead to scan")
    parser.add_argument("--min-form", type=int, default=3, help="Minimum home/away form matches")
    parser.add_argument("--all-leagues", action="store_true", help="Include non-major leagues")
    parser.add_argument("--config", type=Path, default=Path("config/odds.yaml"))
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--show-all", action="store_true", help="Show all fair-odds candidates")
    args = parser.parse_args()

    scan_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()
    config = ScanConfig(
        min_odds=args.min_odds,
        max_odds=args.max_odds,
        min_value_pct=args.min_value,
        major_only=not args.all_leagues,
        scan_days=args.days,
        min_form_matches=args.min_form,
    )
    manual_odds = _load_manual_odds(args.config)

    results = scan(scan_date=scan_date, config=config, manual_odds=manual_odds)
    best = pick_best_daily_bet(results)

    if args.json:
        payload = {
            "scan_date": scan_date.isoformat(),
            "fixtures_analyzed": len(results),
            "best_pick": None,
            "results": [],
        }
        for result in results:
            entry = {
                "league": result.fixture.league,
                "match": f"{result.fixture.home_name} vs {result.fixture.away_name}",
                "kickoff_utc": result.fixture.kickoff_utc,
                "odds_source": result.odds_source,
                "value_bets": [bet.__dict__ for bet in result.value_bets],
                "fair_markets_in_range": [m for m in result.fair_markets if m["in_target_range"]],
            }
            payload["results"].append(entry)

        if best:
            top_bet = best.value_bets[0] if best.value_bets else None
            top_fair = next((m for m in best.fair_markets if m["in_target_range"]), None)
            payload["best_pick"] = {
                "match": f"{best.fixture.home_name} vs {best.fixture.away_name}",
                "league": best.fixture.league,
                "value_bet": top_bet.__dict__ if top_bet else None,
                "model_suggestion": top_fair,
            }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print(f"Value Bet Scanner | {scan_date.isoformat()} | {len(results)} upcoming fixtures")
    print(f"Filters: odds {config.min_odds}-{config.max_odds} | min value +{config.min_value_pct}%")

    if not results:
        print("\nΔεν βρέθηκαν επερχόμενα ματς σε major leagues.")
        return 0

    has_value = any(result.value_bets for result in results)
    if has_value:
        for result in results:
            if result.value_bets:
                _print_fixture(result)
    else:
        print("\nΔεν βρέθηκαν value bets με πραγματικές αποδόσεις.")
        print("Tip: βάλε THE_ODDS_API_KEY ή πρόσθεσε αποδόσεις στο config/odds.yaml")
        if args.show_all or True:
            for result in results:
                fair = [m for m in result.fair_markets if m["in_target_range"]]
                if fair:
                    _print_fixture(result, show_all=True)

    if best:
        print(f"\n{'#' * 72}")
        print("ΠΡΟΤΑΣΗ ΗΜΕΡΑΣ")
        print(f"{best.fixture.league}: {best.fixture.home_name} vs {best.fixture.away_name}")
        if best.value_bets:
            bet = best.value_bets[0]
            print(
                f"→ {bet.market} / {bet.selection} @ {bet.odds} | value +{bet.value_pct}% | "
                f"model {bet.model_probability}%"
            )
        else:
            suggestion = next((m for m in best.fair_markets if m["in_target_range"]), None)
            if suggestion:
                print(
                    f"→ {suggestion['market']} / {suggestion['selection']} | "
                    f"fair odds {suggestion['fair_odds']} (model {suggestion['probability_pct']}%)"
                )
                print("  Βάλε την απόδοση από Stoiximan/Betano στο config/odds.yaml για value check.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
