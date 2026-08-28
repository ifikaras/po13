#!/usr/bin/env python3
"""CLI for daily value bet scanning (Novibet-first workflow)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

import yaml

from value_scanner.scanner import ScanConfig, load_novibet_matches, pick_best_daily_bet, scan


def _load_legacy_odds(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    return data.get("matches", {})


def _match_label(result) -> str:
    return f"{result.novibet_match.home} vs {result.novibet_match.away}"


def _league_label(result) -> str:
    if result.fixture:
        return result.fixture.league
    if result.novibet_match.league:
        return result.novibet_match.league
    return result.novibet_match.sport


def _print_fixture(result, show_all: bool = False) -> None:
    novibet = result.novibet_match
    print(f"\n{'=' * 72}")
    print(f"[Novibet] {_league_label(result)} | {_match_label(result)}")
    if result.fixture:
        fixture = result.fixture
        print(f"Kickoff UTC: {fixture.kickoff_utc}")
        print(
            f"Form (home): {fixture.home_name} {fixture.home_form.scored:.2f} GF / "
            f"{fixture.home_form.conceded:.2f} GA ({fixture.home_form.matches_used} matches)"
        )
        print(
            f"Form (away): {fixture.away_name} {fixture.away_form.scored:.2f} GF / "
            f"{fixture.away_form.conceded:.2f} GA ({fixture.away_form.matches_used} matches)"
        )
    else:
        print(f"Sport: {novibet.sport} | (χωρίς στατιστικά FotMob — μόνο manual model_probability)")

    if result.probabilities:
        probs = result.probabilities
        print(
            f"Expected goals: {probs.lambda_home:.2f} - {probs.lambda_away:.2f} | "
            f"Over 2.5: {probs.over_25 * 100:.1f}% | BTTS: {probs.btts_yes * 100:.1f}%"
        )

    print(f"Odds source: {result.odds_source}")

    if result.value_bets:
        print("\nVALUE BETS (Novibet):")
        for bet in result.value_bets:
            print(
                f"  • {bet.market} / {bet.selection} @ {bet.odds} | "
                f"model {bet.model_probability}% vs implied {bet.implied_probability}% | "
                f"value +{bet.value_pct}% | fair odds {bet.fair_odds}"
            )
    elif show_all and result.stats_available:
        print("\nFair odds στο range — έλεγξε τις αποδόσεις στη Novibet:")
        for market in result.fair_markets:
            if market["in_target_range"]:
                print(
                    f"  • {market['market']} / {market['selection']} | "
                    f"model {market['probability_pct']}% | fair odds {market['fair_odds']}"
                )


def _import_legacy_odds_to_novibet(novibet_path: Path, legacy_path: Path) -> None:
    legacy = _load_legacy_odds(legacy_path)
    if not legacy:
        return

    with novibet_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if data.get("matches"):
        return

    data["matches_dict"] = legacy
    with novibet_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Novibet value bet scanner — ό,τι παίζεις στη Novibet, όχι συγκεκριμένα πρωταθλήματα"
    )
    parser.add_argument("--date", help="Scan date YYYY-MM-DD (default: today)")
    parser.add_argument("--min-odds", type=float, default=1.40)
    parser.add_argument(
        "--max-odds",
        type=float,
        default=None,
        help="Optional upper odds cap (default: none — edge tiers decide plays)",
    )
    parser.add_argument("--min-value", type=float, default=3.0, help="Minimum value %%")
    parser.add_argument("--days", type=int, default=1, help="Days ahead to scan")
    parser.add_argument("--min-form", type=int, default=3, help="Minimum home/away form matches")
    parser.add_argument(
        "--major-only",
        action="store_true",
        help="Limit FotMob search to major European leagues only",
    )
    parser.add_argument(
        "--scan-all-football",
        action="store_true",
        help="Scan all football with odds in config (not Novibet-only)",
    )
    parser.add_argument("--config", type=Path, default=Path("config/novibet.yaml"))
    parser.add_argument("--legacy-config", type=Path, default=Path("config/odds.yaml"))
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--show-all", action="store_true", help="Show all fair-odds candidates")
    parser.add_argument(
        "--list-novibet",
        action="store_true",
        help="Show loaded Novibet matches from config/API",
    )
    args = parser.parse_args()

    _import_legacy_odds_to_novibet(args.config, args.legacy_config)

    scan_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()
    config = ScanConfig(
        min_odds=args.min_odds,
        max_odds=args.max_odds,
        min_value_pct=args.min_value,
        major_only=args.major_only,
        scan_days=args.days,
        min_form_matches=args.min_form,
        novibet_only=not args.scan_all_football,
    )

    if args.list_novibet:
        matches = load_novibet_matches(args.config)
        print(f"Novibet matches loaded: {len(matches)}")
        for match in matches:
            print(f"  • [{match.sport}] {match.home} vs {match.away} ({match.source})")
        if not matches:
            print("  Κανένα — πρόσθεσε στο config/novibet.yaml ή βάλε ODDS_API_IO_KEY")
        return 0

    manual_odds = _load_legacy_odds(args.legacy_config)
    results = scan(
        scan_date=scan_date,
        config=config,
        manual_odds=manual_odds,
        novibet_config=args.config,
    )
    best = pick_best_daily_bet(results)

    if args.json:
        payload = {
            "scan_date": scan_date.isoformat(),
            "mode": "novibet" if config.novibet_only else "all-football",
            "fixtures_analyzed": len(results),
            "best_pick": None,
            "results": [],
        }
        for result in results:
            entry = {
                "league": _league_label(result),
                "match": _match_label(result),
                "sport": result.novibet_match.sport,
                "kickoff_utc": result.fixture.kickoff_utc if result.fixture else None,
                "odds_source": result.odds_source,
                "stats_available": result.stats_available,
                "value_bets": [bet.__dict__ for bet in result.value_bets],
                "fair_markets_in_range": [m for m in result.fair_markets if m["in_target_range"]],
            }
            payload["results"].append(entry)

        if best:
            top_bet = best.value_bets[0] if best.value_bets else None
            top_fair = next((m for m in best.fair_markets if m["in_target_range"]), None)
            payload["best_pick"] = {
                "match": _match_label(best),
                "league": _league_label(best),
                "value_bet": top_bet.__dict__ if top_bet else None,
                "model_suggestion": top_fair,
            }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    mode = "Novibet-only" if config.novibet_only else "All football"
    print(f"Value Bet Scanner | {scan_date.isoformat()} | {mode} | {len(results)} matches")
    odds_range = f"{config.min_odds}+" if config.max_odds is None else f"{config.min_odds}-{config.max_odds}"
    print(f"Filters: odds {odds_range} | min value +{config.min_value_pct}% (+ tier thresholds)")

    if not results:
        print("\nΔεν βρέθηκαν αγώνες Novibet για ανάλυση.")
        print("1. Άνοιξε novibet.gr και διάλεξε στοίχημα")
        print("2. Πρόσθεσέ το στο config/novibet.yaml (ομάδες + αποδόσεις)")
        print("3. Τρέξε ξανά: python -m value_scanner.cli")
        print("Εναλλακτικά: ODDS_API_IO_KEY για αυτόματη λήψη Novibet odds")
        return 0

    has_value = any(result.value_bets for result in results)
    if has_value:
        for result in results:
            if result.value_bets:
                _print_fixture(result)
    else:
        print("\nΔεν βρέθηκαν value bets — έλεγξε τις αποδόσεις Novibet στο config.")
        for result in results:
            fair = [m for m in result.fair_markets if m["in_target_range"]]
            if fair or args.show_all:
                _print_fixture(result, show_all=True)

    if best:
        print(f"\n{'#' * 72}")
        print("ΠΡΟΤΑΣΗ ΗΜΕΡΑΣ (Novibet)")
        print(f"{_league_label(best)}: {_match_label(best)}")
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
                print("  Βάλε την απόδοση Novibet στο config/novibet.yaml για value check.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
