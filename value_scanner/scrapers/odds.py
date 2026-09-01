"""Odds providers: The Odds API and manual config."""

from __future__ import annotations

import os
from dataclasses import dataclass

from value_scanner.http_client import get_json

SPORT_KEYS = {
    "ENG": "soccer_epl",
    "ESP": "soccer_spain_la_liga",
    "GER": "soccer_germany_bundesliga",
    "ITA": "soccer_italy_serie_a",
    "FRA": "soccer_france_ligue_one",
    "NED": "soccer_netherlands_eredivisie",
    "POR": "soccer_portugal_primeira_liga",
    "GRC": "soccer_greece_super_league",
}


@dataclass
class MarketOdds:
    home_win: float | None = None
    draw: float | None = None
    away_win: float | None = None
    over_25: float | None = None
    under_25: float | None = None
    btts_yes: float | None = None
    btts_no: float | None = None
    dc_1x: float | None = None
    dc_x2: float | None = None
    dc_12: float | None = None
    source: str = "unknown"


def _normalize_name(name: str) -> str:
    return "".join(ch.lower() for ch in name if ch.isalnum())


def _best_outcome_prices(bookmakers: list[dict], market_key: str, outcome_names: list[str]) -> list[float | None]:
    best: list[float | None] = [None] * len(outcome_names)
    normalized_targets = [_normalize_name(name) for name in outcome_names]

    for bookmaker in bookmakers:
        for market in bookmaker.get("markets", []):
            if market.get("key") != market_key:
                continue
            for outcome in market.get("outcomes", []):
                outcome_name = _normalize_name(outcome.get("name", ""))
                price = outcome.get("price")
                if price is None:
                    continue
                for index, target in enumerate(normalized_targets):
                    if outcome_name == target or target in outcome_name or outcome_name in target:
                        if best[index] is None or price > best[index]:
                            best[index] = float(price)
    return best


def fetch_odds_from_api(league_code: str, home_name: str, away_name: str) -> MarketOdds | None:
    api_key = os.getenv("THE_ODDS_API_KEY")
    sport = SPORT_KEYS.get(league_code)
    if not api_key or not sport:
        return None

    url = (
        "https://api.the-odds-api.com/v4/sports/"
        f"{sport}/odds?apiKey={api_key}&regions=eu&markets=h2h,totals&oddsFormat=decimal"
    )
    try:
        events = get_json(url)
    except Exception:
        return None

    home_norm = _normalize_name(home_name)
    away_norm = _normalize_name(away_name)

    for event in events:
        event_home = _normalize_name(event.get("home_team", ""))
        event_away = _normalize_name(event.get("away_team", ""))
        if home_norm not in event_home and event_home not in home_norm:
            continue
        if away_norm not in event_away and event_away not in away_norm:
            continue

        bookmakers = event.get("bookmakers", [])
        h2h = _best_outcome_prices(bookmakers, "h2h", [home_name, "Draw", away_name])
        totals = _best_outcome_prices(bookmakers, "totals", ["Over", "Under"])

        over_25 = under_25 = None
        for bookmaker in bookmakers:
            for market in bookmaker.get("markets", []):
                if market.get("key") != "totals":
                    continue
                for outcome in market.get("outcomes", []):
                    if outcome.get("point") == 2.5:
                        if outcome.get("name", "").lower().startswith("over"):
                            over_25 = max(over_25 or 0, float(outcome["price"]))
                        elif outcome.get("name", "").lower().startswith("under"):
                            under_25 = max(under_25 or 0, float(outcome["price"]))

        if totals[0] and over_25 is None:
            over_25 = totals[0]
        if totals[1] and under_25 is None:
            under_25 = totals[1]

        return MarketOdds(
            home_win=h2h[0],
            draw=h2h[1],
            away_win=h2h[2],
            over_25=over_25,
            under_25=under_25,
            source="the-odds-api",
        )

    return None


def manual_odds_lookup(manual_map: dict[str, dict], home_name: str, away_name: str) -> MarketOdds | None:
    keys = [
        f"{home_name} vs {away_name}",
        f"{_normalize_name(home_name)} vs {_normalize_name(away_name)}",
        _normalize_name(f"{home_name}{away_name}"),
    ]
    for key in keys:
        if key in manual_map:
            data = manual_map[key]
            return MarketOdds(
                home_win=data.get("home_win"),
                draw=data.get("draw"),
                away_win=data.get("away_win"),
                over_25=data.get("over_25"),
                under_25=data.get("under_25"),
                btts_yes=data.get("btts_yes"),
                btts_no=data.get("btts_no"),
                dc_1x=data.get("dc_1x"),
                dc_x2=data.get("dc_x2"),
                dc_12=data.get("dc_12"),
                source="manual",
            )
    return None
