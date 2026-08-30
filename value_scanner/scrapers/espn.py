"""ESPN scoreboard data for basketball, NFL, NHL, MLB."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from value_scanner.http_client import get_json
from value_scanner.sports_config import ESPN_LEAGUES, EspnLeagueConfig

# Backward-compatible export for daily_pick.
ESPN_SPORTS = [(c.sport_path, c.league_path, c.league_name) for c in ESPN_LEAGUES]


@dataclass
class EspnEvent:
    sport: str
    league: str
    home: str
    away: str
    kickoff_utc: str
    home_id: str
    away_id: str
    status: str
    sport_path: str = ""
    league_path: str = ""


def _format_espn_date(value: date) -> str:
    return value.strftime("%Y%m%d")


def fetch_espn_events(scan_date: date | None = None) -> list[EspnEvent]:
    scan_date = scan_date or date.today()
    date_param = _format_espn_date(scan_date)
    events: list[EspnEvent] = []

    for cfg in ESPN_LEAGUES:
        url = (
            f"https://site.api.espn.com/apis/site/v2/sports/{cfg.sport_path}/"
            f"{cfg.league_path}/scoreboard?dates={date_param}"
        )
        try:
            payload = get_json(url)
        except Exception:
            continue

        for event in payload.get("events", []):
            status_type = event.get("status", {}).get("type", {})
            if status_type.get("completed"):
                continue
            if status_type.get("state") == "in":
                continue

            competition = (event.get("competitions") or [{}])[0]
            competitors = competition.get("competitors") or []
            home = away = None
            home_id = away_id = ""

            for competitor in competitors:
                team = competitor.get("team", {})
                name = team.get("displayName") or team.get("name") or ""
                tid = str(team.get("id", ""))
                if competitor.get("homeAway") == "home":
                    home = name
                    home_id = tid
                elif competitor.get("homeAway") == "away":
                    away = name
                    away_id = tid

            if not home or not away:
                continue

            events.append(
                EspnEvent(
                    sport=cfg.sport_key,
                    league=cfg.league_name,
                    home=home,
                    away=away,
                    kickoff_utc=event.get("date", ""),
                    home_id=home_id,
                    away_id=away_id,
                    status=status_type.get("description", "scheduled"),
                    sport_path=cfg.sport_path,
                    league_path=cfg.league_path,
                )
            )

    return events


def league_config_for(event: EspnEvent) -> EspnLeagueConfig | None:
    for cfg in ESPN_LEAGUES:
        if cfg.league_name == event.league and cfg.sport_key == event.sport:
            return cfg
    return None


def fetch_team_win_rate(sport_path: str, league_path: str, team_id: str) -> float | None:
    if not team_id:
        return None
    try:
        payload = get_json(
            f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/"
            f"{league_path}/teams/{team_id}"
        )
    except Exception:
        return None

    team = payload.get("team", {})
    record = team.get("record", {})
    items = record.get("items", [])
    for item in items:
        stats = item.get("stats", [])
        wins = losses = None
        for stat in stats:
            if stat.get("name") == "wins":
                wins = stat.get("value")
            if stat.get("name") == "losses":
                losses = stat.get("value")
        if wins is not None and losses is not None and (wins + losses) > 0:
            return wins / (wins + losses)

    return None
