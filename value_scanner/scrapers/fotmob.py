"""FotMob data fetcher for fixtures and team form."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache

from value_scanner.http_client import get_json

MAJOR_LEAGUE_CODES = {"ENG", "ESP", "GER", "ITA", "FRA", "NED", "POR", "GRC", "BEL", "TUR", "SCO"}
MAJOR_LEAGUE_NAMES = {
    "Premier League",
    "LaLiga",
    "Bundesliga",
    "Serie A",
    "Ligue 1",
    "Eredivisie",
    "Primeira Liga",
    "Super League 1",
    "Pro League",
    "Championship",
    "2. Bundesliga",
    "Serie B",
    "LaLiga 2",
    "Liga Portugal",
}

# Strict whitelist avoids hundreds of homonymous "Premier League" competitions.
TOP_LEAGUE_IDS = {
    47,   # Premier League
    87,   # LaLiga
    54,   # Bundesliga
    55,   # Serie A
    53,   # Ligue 1
    57,   # Eredivisie
    61,   # Liga Portugal
    135,  # Super League 1 (Greece)
    48,   # Championship
    146,  # 2. Bundesliga
    140,  # LaLiga 2
    86,   # Serie B
}


@dataclass
class TeamFormStats:
    scored: float
    conceded: float
    matches_used: int


@dataclass
class Fixture:
    match_id: int
    league: str
    league_code: str
    kickoff_utc: str
    home_id: int
    home_name: str
    away_id: int
    away_name: str
    home_form: TeamFormStats
    away_form: TeamFormStats


def _format_date(value: date) -> str:
    return value.strftime("%Y%m%d")


def _parse_score(score_str: str) -> tuple[int, int]:
    left, right = score_str.split("-")
    return int(left.strip()), int(right.strip())


def _team_form_stats(team_id: int, venue: str, form_matches: list[dict], limit: int = 5) -> TeamFormStats:
    venue_stats = _team_form_stats_for_venue(team_id, venue, form_matches, limit)
    if venue_stats.matches_used >= 3:
        return venue_stats

    overall_stats = _team_form_stats_for_venue(team_id, "any", form_matches, limit)
    if overall_stats.matches_used == 0:
        return TeamFormStats(scored=1.2, conceded=1.2, matches_used=0)

    if venue_stats.matches_used == 0:
        return overall_stats

    # Blend venue-specific and overall form when sample is thin.
    weight = venue_stats.matches_used / 3.0
    return TeamFormStats(
        scored=(venue_stats.scored * weight) + (overall_stats.scored * (1 - weight)),
        conceded=(venue_stats.conceded * weight) + (overall_stats.conceded * (1 - weight)),
        matches_used=overall_stats.matches_used,
    )


def _team_form_stats_for_venue(
    team_id: int,
    venue: str,
    form_matches: list[dict],
    limit: int,
) -> TeamFormStats:
    scored_total = 0.0
    conceded_total = 0.0
    used = 0

    for match in form_matches:
        tooltip = match.get("tooltipText") or {}
        home_id = tooltip.get("homeTeamId")
        away_id = tooltip.get("awayTeamId")
        home_score = tooltip.get("homeScore")
        away_score = tooltip.get("awayScore")

        if home_score is None or away_score is None:
            score_str = match.get("score", "")
            if "-" not in score_str:
                continue
            home_score, away_score = _parse_score(score_str)
            home = match.get("home") or {}
            away = match.get("away") or {}
            home_id = home.get("id")
            away_id = away.get("id")

        if team_id == home_id:
            if venue == "away":
                continue
            scored_total += home_score
            conceded_total += away_score
            used += 1
        elif team_id == away_id:
            if venue == "home":
                continue
            scored_total += away_score
            conceded_total += home_score
            used += 1
        else:
            continue

        if used >= limit:
            break

    if used == 0:
        return TeamFormStats(scored=1.2, conceded=1.2, matches_used=0)

    return TeamFormStats(
        scored=scored_total / used,
        conceded=conceded_total / used,
        matches_used=used,
    )


@lru_cache(maxsize=256)
def _fetch_team_form(team_id: int) -> tuple[dict, ...]:
    payload = get_json(f"https://www.fotmob.com/api/data/teams?id={team_id}")
    overview = payload.get("overview") or {}
    return tuple(overview.get("teamForm") or [])


def _is_upcoming(status: dict) -> bool:
    return not status.get("finished", False) and not status.get("started", False)


def _is_major_league(league: dict) -> bool:
    if league.get("id") in TOP_LEAGUE_IDS:
        return True
    if league.get("ccode") in MAJOR_LEAGUE_CODES and league.get("name") in MAJOR_LEAGUE_NAMES:
        return True
    return False


def _prefetch_team_forms(team_ids: set[int]) -> None:
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(_fetch_team_form, team_id) for team_id in team_ids]
        for future in as_completed(futures):
            future.result()


def fetch_upcoming_fixtures(
    scan_date: date | None = None,
    major_only: bool = True,
    form_limit: int = 5,
) -> list[Fixture]:
    scan_date = scan_date or date.today()
    payload = get_json(f"https://www.fotmob.com/api/data/matches?date={_format_date(scan_date)}")
    raw_matches: list[tuple[dict, dict]] = []

    for league in payload.get("leagues", []):
        if major_only and not _is_major_league(league):
            continue

        for match in league.get("matches", []):
            status = match.get("status") or {}
            if not _is_upcoming(status):
                continue
            raw_matches.append((league, match))

    team_ids = {
        match["home"]["id"]
        for _, match in raw_matches
    } | {
        match["away"]["id"]
        for _, match in raw_matches
    }
    _prefetch_team_forms(team_ids)

    fixtures: list[Fixture] = []
    for league, match in raw_matches:
        home = match["home"]
        away = match["away"]
        status = match.get("status") or {}
        home_form_raw = list(_fetch_team_form(home["id"]))
        away_form_raw = list(_fetch_team_form(away["id"]))

        fixtures.append(
            Fixture(
                match_id=match["id"],
                league=league["name"],
                league_code=league.get("ccode") or "",
                kickoff_utc=status.get("utcTime") or match.get("time", ""),
                home_id=home["id"],
                home_name=home.get("longName") or home["name"],
                away_id=away["id"],
                away_name=away.get("longName") or away["name"],
                home_form=_team_form_stats(home["id"], "home", home_form_raw, form_limit),
                away_form=_team_form_stats(away["id"], "away", away_form_raw, form_limit),
            )
        )

    fixtures.sort(key=lambda item: item.kickoff_utc)
    return fixtures


def fetch_fixtures_for_dates(
    start: date,
    days: int = 2,
    major_only: bool = True,
    form_limit: int = 5,
) -> list[Fixture]:
    fixtures: list[Fixture] = []
    for offset in range(days):
        day = date.fromordinal(start.toordinal() + offset)
        fixtures.extend(fetch_upcoming_fixtures(day, major_only=major_only, form_limit=form_limit))
    return fixtures
