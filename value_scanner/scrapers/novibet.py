"""Novibet odds: manual config and odds-api.io integration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from value_scanner.http_client import get_json
from value_scanner.scrapers.odds import MarketOdds, _normalize_name

NOVIBET_BOOKMAKER = "Novibet"


@dataclass
class NovibetMatch:
    home: str
    away: str
    sport: str = "football"
    league: str = ""
    odds: MarketOdds = field(default_factory=MarketOdds)
    model_probability: dict[str, float] = field(default_factory=dict)
    source: str = "manual"


def _market_odds_from_dict(data: dict[str, Any]) -> MarketOdds:
    return MarketOdds(
        home_win=_to_float(data.get("home_win")),
        draw=_to_float(data.get("draw")),
        away_win=_to_float(data.get("away_win")),
        over_25=_to_float(data.get("over_25")),
        under_25=_to_float(data.get("under_25")),
        btts_yes=_to_float(data.get("btts_yes")),
        btts_no=_to_float(data.get("btts_no")),
        dc_1x=_to_float(data.get("dc_1x")),
        dc_x2=_to_float(data.get("dc_x2")),
        dc_12=_to_float(data.get("dc_12")),
        source="novibet-manual",
    )


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_novibet_config(path: Path) -> list[NovibetMatch]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    matches: list[NovibetMatch] = []
    for entry in data.get("matches", []):
        if isinstance(entry, dict) and "home" in entry and "away" in entry:
            odds_data = entry.get("odds") or {}
            model_probs = entry.get("model_probability") or {}
            matches.append(
                NovibetMatch(
                    home=str(entry["home"]),
                    away=str(entry["away"]),
                    sport=str(entry.get("sport", "football")),
                    league=str(entry.get("league", "")),
                    odds=_market_odds_from_dict(odds_data),
                    model_probability={
                        str(k): float(v) for k, v in model_probs.items() if v is not None
                    },
                    source="novibet-manual",
                )
            )
        elif isinstance(entry, str) and " vs " in entry:
            home, away = entry.split(" vs ", 1)
            matches.append(NovibetMatch(home=home.strip(), away=away.strip()))

    # Legacy flat dict format (config/odds.yaml style)
    for key, odds_data in (data.get("matches_dict") or {}).items():
        if " vs " in key and isinstance(odds_data, dict):
            home, away = key.split(" vs ", 1)
            matches.append(
                NovibetMatch(
                    home=home.strip(),
                    away=away.strip(),
                    odds=_market_odds_from_dict(odds_data),
                    source="novibet-manual",
                )
            )

    return matches


def _parse_odds_api_markets(bookmaker_payload: dict) -> MarketOdds:
    odds = MarketOdds(source="novibet-api")

    for market in bookmaker_payload.get("markets", []) or bookmaker_payload.get("odds", []) or []:
        name = str(market.get("name", "")).lower()
        outcomes = market.get("outcomes") or market.get("odds") or []

        if name in {"moneyline", "1x2", "match result", "match winner"}:
            for outcome in outcomes:
                label = str(outcome.get("name", outcome.get("label", ""))).lower()
                price = _to_float(outcome.get("price") or outcome.get("odd") or outcome.get("value"))
                if "draw" in label or label == "x":
                    odds.draw = price
                elif outcome.get("home") or label == "1":
                    odds.home_win = _to_float(outcome.get("home") or price)
                elif outcome.get("away") or label == "2":
                    odds.away_win = _to_float(outcome.get("away") or price)

        if "total" in name or name == "totals":
            for outcome in outcomes:
                point = outcome.get("hdp") or outcome.get("point")
                if point is not None and float(point) != 2.5:
                    continue
                label = str(outcome.get("name", "")).lower()
                price = _to_float(outcome.get("price") or outcome.get("over") or outcome.get("under"))
                if "over" in label:
                    odds.over_25 = _to_float(outcome.get("over") or price)
                elif "under" in label:
                    odds.under_25 = _to_float(outcome.get("under") or price)

        if "both" in name or name == "bts" or name == "btts":
            for outcome in outcomes:
                label = str(outcome.get("name", "")).lower()
                price = _to_float(outcome.get("price"))
                if label in {"yes", "y"}:
                    odds.btts_yes = price
                elif label in {"no", "n"}:
                    odds.btts_no = price

    return odds


def fetch_novibet_from_odds_api(sports: list[str] | None = None) -> list[NovibetMatch]:
    api_key = os.getenv("ODDS_API_IO_KEY")
    if not api_key:
        return []

    sports = sports or [
        "football",
        "basketball",
        "tennis",
        "ice-hockey",
        "baseball",
        "volleyball",
        "handball",
    ]

    matches: list[NovibetMatch] = []
    seen: set[str] = set()

    for sport in sports:
        try:
            events = get_json(
                f"https://api.odds-api.io/v3/events?apiKey={api_key}&sport={sport}&limit=100"
            )
        except Exception:
            continue

        if not isinstance(events, list):
            events = events.get("events") or events.get("data") or []

        for event in events:
            event_id = event.get("id")
            home = event.get("home") or event.get("homeTeam") or event.get("home_team")
            away = event.get("away") or event.get("awayTeam") or event.get("away_team")
            if not event_id or not home or not away:
                continue

            home_name = home if isinstance(home, str) else home.get("name", "")
            away_name = away if isinstance(away, str) else away.get("name", "")
            dedupe = _normalize_name(f"{home_name}{away_name}")
            if dedupe in seen:
                continue
            seen.add(dedupe)

            try:
                odds_payload = get_json(
                    f"https://api.odds-api.io/v3/odds?apiKey={api_key}"
                    f"&eventId={event_id}&bookmakers={NOVIBET_BOOKMAKER}"
                )
            except Exception:
                continue

            bookmakers = odds_payload.get("bookmakers") or odds_payload
            novibet_data = None
            if isinstance(bookmakers, dict):
                novibet_data = bookmakers.get(NOVIBET_BOOKMAKER) or bookmakers.get("novibet")
            elif isinstance(bookmakers, list):
                for book in bookmakers:
                    name = str(book.get("name", "")).lower()
                    if "novibet" in name:
                        novibet_data = book
                        break

            if not novibet_data:
                continue

            league = event.get("league") or {}
            league_name = league.get("name", "") if isinstance(league, dict) else str(league)

            matches.append(
                NovibetMatch(
                    home=home_name,
                    away=away_name,
                    sport=sport,
                    league=league_name,
                    odds=_parse_odds_api_markets(novibet_data),
                    source="novibet-api",
                )
            )

    return matches


def merge_novibet_sources(manual: list[NovibetMatch], api: list[NovibetMatch]) -> list[NovibetMatch]:
    merged: dict[str, NovibetMatch] = {}

    for match in api:
        key = _normalize_name(f"{match.home}{match.away}")
        merged[key] = match

    for match in manual:
        key = _normalize_name(f"{match.home}{match.away}")
        if key in merged:
            existing = merged[key]
            for field_name in MarketOdds.__dataclass_fields__:
                if field_name == "source":
                    continue
                manual_val = getattr(match.odds, field_name)
                if manual_val is not None:
                    setattr(existing.odds, field_name, manual_val)
            existing.model_probability.update(match.model_probability)
            existing.source = "novibet-manual+api"
        else:
            merged[key] = match

    return list(merged.values())
