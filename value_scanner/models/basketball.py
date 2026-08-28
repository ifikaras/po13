"""Simple basketball win probability from team win rates."""

from __future__ import annotations

HOME_COURT_BOOST = 0.06


def home_win_probability(home_win_rate: float, away_win_rate: float) -> float:
    home = max(home_win_rate, 0.15) + HOME_COURT_BOOST
    away = max(away_win_rate, 0.15)
    return home / (home + away)


def away_win_probability(home_win_rate: float, away_win_rate: float) -> float:
    return 1.0 - home_win_probability(home_win_rate, away_win_rate)
