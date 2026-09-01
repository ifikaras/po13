"""Poisson-based match outcome probabilities."""

from __future__ import annotations

from dataclasses import dataclass

from scipy.stats import poisson


@dataclass(frozen=True)
class MatchProbabilities:
    home_win: float
    draw: float
    away_win: float
    over_25: float
    under_25: float
    btts_yes: float
    btts_no: float
    dc_1x: float
    dc_x2: float
    dc_12: float
    lambda_home: float
    lambda_away: float


def _score_matrix(lambda_home: float, lambda_away: float, max_goals: int = 10) -> dict[tuple[int, int], float]:
    matrix: dict[tuple[int, int], float] = {}
    for home_goals in range(max_goals + 1):
        p_home = poisson.pmf(home_goals, lambda_home)
        for away_goals in range(max_goals + 1):
            matrix[(home_goals, away_goals)] = p_home * poisson.pmf(away_goals, lambda_away)
    return matrix


def estimate_lambdas(
    home_scored: float,
    home_conceded: float,
    away_scored: float,
    away_conceded: float,
    league_avg: float = 2.65,
    home_advantage: float = 1.12,
) -> tuple[float, float]:
    """Estimate expected goals from rolling home/away form averages."""
    home_attack = max(home_scored, 0.3)
    home_defense = max(home_conceded, 0.3)
    away_attack = max(away_scored, 0.3)
    away_defense = max(away_conceded, 0.3)

    scale = league_avg / 2.0
    lambda_home = (home_attack * away_defense / scale) * home_advantage
    lambda_away = (away_attack * home_defense / scale) / home_advantage
    return max(lambda_home, 0.15), max(lambda_away, 0.15)


def calculate_probabilities(lambda_home: float, lambda_away: float) -> MatchProbabilities:
    matrix = _score_matrix(lambda_home, lambda_away)

    home_win = draw = away_win = 0.0
    over_25 = under_25 = 0.0
    btts_yes = btts_no = 0.0

    for (home_goals, away_goals), prob in matrix.items():
        total = home_goals + away_goals
        if home_goals > away_goals:
            home_win += prob
        elif home_goals == away_goals:
            draw += prob
        else:
            away_win += prob

        if total > 2.5:
            over_25 += prob
        else:
            under_25 += prob

        if home_goals >= 1 and away_goals >= 1:
            btts_yes += prob
        else:
            btts_no += prob

    return MatchProbabilities(
        home_win=home_win,
        draw=draw,
        away_win=away_win,
        over_25=over_25,
        under_25=under_25,
        btts_yes=btts_yes,
        btts_no=btts_no,
        dc_1x=home_win + draw,
        dc_x2=draw + away_win,
        dc_12=home_win + away_win,
        lambda_home=lambda_home,
        lambda_away=lambda_away,
    )


def fair_odds(probability: float) -> float | None:
    if probability <= 0:
        return None
    return round(1.0 / probability, 2)
