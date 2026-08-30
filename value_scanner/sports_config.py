"""Sport metadata for multi-sport scan board."""

from __future__ import annotations

from dataclasses import dataclass

# pinnapi sport ids (mirrored in scrapers/pinnacle.py)
SPORT_SOCCER = 1
SPORT_TENNIS = 2
SPORT_BASKETBALL = 3
SPORT_HOCKEY = 4
SPORT_BASEBALL = 5


@dataclass(frozen=True)
class EspnLeagueConfig:
    sport_path: str
    league_path: str
    league_name: str
    sport_key: str
    pinnacle_sport_id: int
    home_advantage: float = 0.05


ESPN_LEAGUES: tuple[EspnLeagueConfig, ...] = (
    EspnLeagueConfig("basketball", "nba", "NBA", "basketball", SPORT_BASKETBALL, 0.06),
    EspnLeagueConfig("basketball", "wnba", "WNBA", "basketball", SPORT_BASKETBALL, 0.05),
    EspnLeagueConfig("football", "nfl", "NFL", "american_football", SPORT_BASEBALL, 0.04),
    EspnLeagueConfig("hockey", "nhl", "NHL", "hockey", SPORT_HOCKEY, 0.05),
    EspnLeagueConfig("baseball", "mlb", "MLB", "baseball", SPORT_BASEBALL, 0.04),
)

SPORT_LABELS_GREEK: dict[str, str] = {
    "football": "Ποδόσφαιρο",
    "basketball": "Μπάσκετ",
    "tennis": "Τένις",
    "hockey": "Χόκεϊ",
    "baseball": "Μπέιζμπολ",
    "american_football": "NFL",
}

SPORT_EMOJI: dict[str, str] = {
    "football": "⚽",
    "basketball": "🏀",
    "tennis": "🎾",
    "hockey": "🏒",
    "baseball": "⚾",
    "american_football": "🏈",
}

# pinnapi sport_id=5 mixes MLB + NFL — filter by league name.
PINNACLE_LEAGUE_FILTERS: dict[str, tuple[str, ...]] = {
    "baseball": ("mlb", "npb", "kbo", "baseball"),
    "american_football": ("nfl",),
}

TENNIS_LEAGUE_HINTS = (
    "atp",
    "wta",
    "grand slam",
    "us open",
    "wimbledon",
    "roland garros",
    "french open",
    "australian open",
    "masters",
    "miami open",
    "indian wells",
)

# Max upcoming entries per non-football sport on the daily board.
MAX_PER_SPORT = 10
