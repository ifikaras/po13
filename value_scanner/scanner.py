"""Main scanning orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from value_scanner.calculator import ValueBet, evaluate_market
from value_scanner.models.poisson import calculate_probabilities, estimate_lambdas, fair_odds
from value_scanner.scrapers.fotmob import Fixture, fetch_fixtures_for_dates
from value_scanner.scrapers.odds import MarketOdds, fetch_odds_from_api, manual_odds_lookup


@dataclass
class ScanConfig:
    min_odds: float = 1.70
    max_odds: float = 1.85
    min_value_pct: float = 3.0
    major_only: bool = True
    form_limit: int = 5
    min_form_matches: int = 3
    scan_days: int = 1


@dataclass
class AnalyzedFixture:
    fixture: Fixture
    probabilities: object
    fair_markets: list[dict]
    value_bets: list[ValueBet] = field(default_factory=list)
    odds: MarketOdds | None = None
    odds_source: str = "model-only"


def _market_definitions(probabilities) -> list[tuple[str, str, float, str]]:
    return [
        ("1X2", "Home Win", probabilities.home_win, "home_win"),
        ("1X2", "Draw", probabilities.draw, "draw"),
        ("1X2", "Away Win", probabilities.away_win, "away_win"),
        ("Over/Under", "Over 2.5", probabilities.over_25, "over_25"),
        ("Over/Under", "Under 2.5", probabilities.under_25, "under_25"),
        ("BTTS", "Yes", probabilities.btts_yes, "btts_yes"),
        ("BTTS", "No", probabilities.btts_no, "btts_no"),
        ("Double Chance", "1X", probabilities.dc_1x, "dc_1x"),
        ("Double Chance", "X2", probabilities.dc_x2, "dc_x2"),
        ("Double Chance", "12", probabilities.dc_12, "dc_12"),
    ]


def analyze_fixture(
    fixture: Fixture,
    config: ScanConfig,
    manual_odds: dict[str, dict] | None = None,
) -> AnalyzedFixture | None:
    if fixture.home_form.matches_used < config.min_form_matches:
        return None
    if fixture.away_form.matches_used < config.min_form_matches:
        return None

    lambda_home, lambda_away = estimate_lambdas(
        fixture.home_form.scored,
        fixture.home_form.conceded,
        fixture.away_form.scored,
        fixture.away_form.conceded,
    )
    probabilities = calculate_probabilities(lambda_home, lambda_away)

    odds = manual_odds_lookup(manual_odds or {}, fixture.home_name, fixture.away_name)
    if odds is None:
        odds = fetch_odds_from_api(fixture.league_code, fixture.home_name, fixture.away_name)

    odds_source = odds.source if odds else "model-only"
    value_bets: list[ValueBet] = []
    fair_markets: list[dict] = []

    for market, selection, model_prob, odds_attr in _market_definitions(probabilities):
        fair = fair_odds(model_prob)
        if fair is None:
            continue

        fair_markets.append(
            {
                "market": market,
                "selection": selection,
                "probability_pct": round(model_prob * 100, 1),
                "fair_odds": fair,
                "in_target_range": config.min_odds <= fair <= config.max_odds,
            }
        )

        if odds is None:
            continue

        book_odds = getattr(odds, odds_attr, None)
        if book_odds is None:
            continue

        bet = evaluate_market(
            market=market,
            selection=selection,
            model_probability=model_prob,
            odds=book_odds,
            min_odds=config.min_odds,
            max_odds=config.max_odds,
            min_value_pct=config.min_value_pct,
        )
        if bet:
            value_bets.append(bet)

    value_bets.sort(key=lambda item: item.value_pct, reverse=True)
    return AnalyzedFixture(
        fixture=fixture,
        probabilities=probabilities,
        fair_markets=fair_markets,
        value_bets=value_bets,
        odds=odds,
        odds_source=odds_source,
    )


def scan(
    scan_date: date | None = None,
    config: ScanConfig | None = None,
    manual_odds: dict[str, dict] | None = None,
) -> list[AnalyzedFixture]:
    config = config or ScanConfig()
    scan_date = scan_date or date.today()
    fixtures = fetch_fixtures_for_dates(
        scan_date,
        days=config.scan_days,
        major_only=config.major_only,
        form_limit=config.form_limit,
    )
    return [
        analyzed
        for fixture in fixtures
        if (analyzed := analyze_fixture(fixture, config, manual_odds)) is not None
    ]


def pick_best_daily_bet(results: list[AnalyzedFixture]) -> AnalyzedFixture | None:
    candidates: list[tuple[ValueBet, AnalyzedFixture]] = []
    for result in results:
        for bet in result.value_bets:
            candidates.append((bet, result))

    if candidates:
        candidates.sort(key=lambda item: item[0].value_pct, reverse=True)
        return candidates[0][1]

    model_candidates: list[tuple[dict, AnalyzedFixture]] = []
    for result in results:
        for market in result.fair_markets:
            if market["in_target_range"]:
                model_candidates.append((market, result))

    if not model_candidates:
        return None

    model_candidates.sort(key=lambda item: item[0]["probability_pct"], reverse=True)
    return model_candidates[0][1]
