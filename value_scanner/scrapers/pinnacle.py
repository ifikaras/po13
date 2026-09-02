"""Pinnacle sharp odds via pinnapi (official Pinnacle API is closed to public).

Auth: set PINNAPI_KEY (preferred) or PINNACLE_API_KEY.
Optional fallback: ODDSPAPI_KEY for OddsPapi bookmakers=pinnacle.

Free trial: https://pinnapi.com — 100 REST req/day, no card.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from value_scanner.http_client import get_json_headers
from value_scanner.matcher import teams_match
from value_scanner.sports_config import PINNACLE_LEAGUE_FILTERS

PINNAPI_BASE = "https://pinnapi.com"

# pinnapi dropping-odds sport ids (NOT the same as Pinnacle internal IDs)
# Docs: https://pinnapi.com/docs — Football (NFL)=5, Baseball (MLB)=6
SPORT_SOCCER = 1
SPORT_TENNIS = 2
SPORT_BASKETBALL = 3
SPORT_HOCKEY = 4
SPORT_AMERICAN_FOOTBALL = 5
SPORT_BASEBALL = 6

SPORT_ID_BY_KEY: dict[str, int] = {
    "football": SPORT_SOCCER,
    "soccer": SPORT_SOCCER,
    "tennis": SPORT_TENNIS,
    "basketball": SPORT_BASKETBALL,
    "hockey": SPORT_HOCKEY,
    "american_football": SPORT_AMERICAN_FOOTBALL,
    "baseball": SPORT_BASEBALL,
}

_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL_SEC = 120.0


@dataclass
class SharpLine:
    """De-vig-ready prices from Pinnacle for one match."""

    home: str
    away: str
    league: str
    kickoff: str
    source: str
    sport_key: str = "football"
    event_id: str | int | None = None
    home_win: float | None = None
    draw: float | None = None
    away_win: float | None = None
    over_25: float | None = None
    under_25: float | None = None
    raw: dict = field(default_factory=dict)

    def moneyline_board(self) -> list[float] | None:
        if self.home_win and self.draw and self.away_win:
            return [self.home_win, self.draw, self.away_win]
        if self.home_win and self.away_win:
            return [self.home_win, self.away_win]
        return None

    def totals_board(self) -> list[float] | None:
        if self.over_25 and self.under_25:
            return [self.over_25, self.under_25]
        return None

    def double_chance_board(self) -> dict[str, float] | None:
        """Build DC prices from moneyline after implied merge (pre-devig soft merge)."""
        if not (self.home_win and self.draw and self.away_win):
            return None
        from value_scanner.market_anchor import multiplicative_devig

        fair = multiplicative_devig([self.home_win, self.draw, self.away_win])
        if len(fair) != 3:
            return None
        p_home, p_draw, p_away = fair
        return {
            "1X": round(1.0 / (p_home + p_draw), 4),
            "X2": round(1.0 / (p_draw + p_away), 4),
            "12": round(1.0 / (p_home + p_away), 4),
            "fair_home": p_home,
            "fair_draw": p_draw,
            "fair_away": p_away,
        }


def pinnacle_configured() -> bool:
    return bool(_pinnapi_key() or _oddspapi_key())


def _pinnapi_key() -> str | None:
    return os.getenv("PINNAPI_KEY") or os.getenv("PINNACLE_API_KEY") or None


def _oddspapi_key() -> str | None:
    return os.getenv("ODDSPAPI_KEY") or None


def _cache_get(key: str) -> Any | None:
    hit = _CACHE.get(key)
    if not hit:
        return None
    ts, value = hit
    if time.time() - ts > _CACHE_TTL_SEC:
        return None
    return value


def _cache_set(key: str, value: Any) -> None:
    _CACHE[key] = (time.time(), value)


def _f(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out > 1.0 else None


def _parse_pinnapi_event(event: dict, sport_key: str) -> SharpLine | None:
    if not event.get("is_have_odds"):
        return None
    periods = event.get("periods") or {}
    full = periods.get("num_0") or periods.get("0") or {}
    money = full.get("money_line") or {}
    totals = full.get("totals") or {}
    total_25 = totals.get("2.5") or totals.get(2.5) or {}
    if not isinstance(total_25, dict):
        total_25 = {}
        for tkey, tobj in totals.items():
            try:
                if abs(float(tkey) - 2.5) < 0.01 and isinstance(tobj, dict):
                    total_25 = tobj
                    break
            except (TypeError, ValueError):
                continue

    home = str(event.get("home") or "")
    away = str(event.get("away") or "")
    if not home or not away:
        return None
    if not (_f(money.get("home")) or _f(money.get("away"))):
        return None

    return SharpLine(
        home=home,
        away=away,
        league=str(event.get("league_name") or ""),
        kickoff=str(event.get("starts") or event.get("start_ts") or ""),
        source="pinnapi",
        sport_key=sport_key,
        event_id=event.get("event_id"),
        home_win=_f(money.get("home")),
        draw=_f(money.get("draw")),
        away_win=_f(money.get("away")),
        over_25=_f(total_25.get("over")),
        under_25=_f(total_25.get("under")),
        raw=event,
    )


def _league_matches_filter(league: str, sport_key: str) -> bool:
    hints = PINNACLE_LEAGUE_FILTERS.get(sport_key)
    if not hints:
        return True
    low = league.lower()
    return any(h in low for h in hints)


def fetch_pinnapi_prematch(
    sport_id: int,
    sport_key: str = "football",
    *,
    league_filter: Callable[[str], bool] | None = None,
) -> list[SharpLine]:
    """Snapshot Pinnacle prematch board for a pinnapi sport_id."""
    key = _pinnapi_key()
    if not key:
        return []

    cache_key = f"pinnapi:{sport_id}:{sport_key}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    url = f"{PINNAPI_BASE}/kit/v1/prematch/fixtures?sport_id={sport_id}"
    try:
        payload = get_json_headers(url, {"x-portal-apikey": key})
    except Exception:
        return []

    lines: list[SharpLine] = []
    for event in payload.get("events") or []:
        line = _parse_pinnapi_event(event, sport_key)
        if line is None:
            continue
        if league_filter is not None:
            if not league_filter(line.league):
                continue
        elif sport_key in PINNACLE_LEAGUE_FILTERS:
            if not _league_matches_filter(line.league, sport_key):
                continue
        lines.append(line)

    _cache_set(cache_key, lines)
    return lines


def fetch_pinnapi_soccer_prematch() -> list[SharpLine]:
    return fetch_pinnapi_prematch(SPORT_SOCCER, "football", league_filter=lambda _: True)


def fetch_pinnapi_by_sport(sport_key: str) -> list[SharpLine]:
    sport_id = SPORT_ID_BY_KEY.get(sport_key)
    if sport_id is None:
        return []
    if sport_key in {"football", "soccer"}:
        return fetch_pinnapi_soccer_prematch()
    return fetch_pinnapi_prematch(sport_id, sport_key)


def find_sharp_line(home: str, away: str, sport: str = "football") -> SharpLine | None:
    """Find Pinnacle line for a match by fuzzy team/player names."""
    sport_l = (sport or "football").lower()
    if sport_l in {"football", "soccer", ""}:
        lines = fetch_pinnapi_soccer_prematch()
    else:
        lines = fetch_pinnapi_by_sport(sport_l)

    for line in lines:
        if teams_match(home, away, line.home, line.away):
            return line
    return None


def sharp_probability_for_selection(
    line: SharpLine,
    market: str,
    selection: str,
) -> tuple[float | None, list[float] | None, int]:
    """Return (market_probability, market_odds_full, selection_index) for anchoring."""
    market_l = market.lower()
    sel_l = selection.lower().strip()

    if "btts" in market_l or "both" in market_l or "σκοράρ" in market_l:
        return None, None, 0

    if "over" in market_l or "under" in market_l or "ο/υ" in market_l or "σύνολο" in market_l:
        board = line.totals_board()
        if not board:
            return None, None, 0
        if "over" in sel_l:
            return None, board, 0
        if "under" in sel_l:
            return None, board, 1
        return None, None, 0

    if "double" in market_l or "διπλή" in market_l or sel_l in {"1x", "x2", "12"}:
        dc = line.double_chance_board()
        if not dc:
            return None, None, 0
        key = selection.upper().replace(" ", "")
        if key in {"1X", "X2", "12"}:
            fair_odds = dc[key]
            return 1.0 / fair_odds, None, 0
        return None, None, 0

    board = line.moneyline_board()
    if not board:
        return None, None, 0

    if len(board) == 2:
        if "home" in sel_l or sel_l in {"1", "home win", "player 1"}:
            return None, board, 0
        if "away" in sel_l or sel_l in {"2", "away win", "player 2"}:
            return None, board, 1
        return None, None, 0

    if len(board) >= 3:
        if "home" in sel_l or sel_l in {"1", "home win"}:
            return None, board, 0
        if "draw" in sel_l or sel_l in {"x"}:
            return None, board, 1
        if "away" in sel_l or sel_l in {"2", "away win"}:
            return None, board, 2
    return None, None, 0


def status_report() -> str:
    if not _pinnapi_key():
        return (
            "Pinnacle: ΟΧΙ ρυθμισμένο. Βάλε secret PINNAPI_KEY από https://pinnapi.com "
            "(δωρεάν 100 req/ημέρα)."
        )
    parts = []
    for label, sid, key in [
        ("soccer", SPORT_SOCCER, "football"),
        ("tennis", SPORT_TENNIS, "tennis"),
        ("basketball", SPORT_BASKETBALL, "basketball"),
        ("hockey", SPORT_HOCKEY, "hockey"),
        ("NFL", SPORT_AMERICAN_FOOTBALL, "american_football"),
        ("baseball", SPORT_BASEBALL, "baseball"),
    ]:
        if key == "football":
            n = len(fetch_pinnapi_soccer_prematch())
        else:
            n = len(fetch_pinnapi_prematch(sid, key))
        parts.append(f"{label} {n}")
    return f"Pinnacle (pinnapi): OK — {', '.join(parts)}"
