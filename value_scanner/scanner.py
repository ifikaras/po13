"""Main scanning orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from value_scanner.calculator import ValueBet, evaluate_market
from value_scanner.matcher import teams_match
from value_scanner.models.poisson import calculate_probabilities, estimate_lambdas, fair_odds
from value_scanner.scrapers.fotmob import (
    Fixture,
    enrich_fixture,
    fetch_fixture_index_for_dates,
    fetch_fixtures_for_dates,
)
from value_scanner.scrapers.novibet import (
    NovibetMatch,
    fetch_novibet_from_odds_api,
    load_novibet_config,
    merge_novibet_sources,
)
from value_scanner.scrapers.odds import MarketOdds, manual_odds_lookup


@dataclass
class ScanConfig:
    min_odds: float = 1.70
    max_odds: float = 1.85
    min_value_pct: float = 3.0
    major_only: bool = False
    form_limit: int = 5
    min_form_matches: int = 3
    scan_days: int = 1
    novibet_only: bool = True


@dataclass
class AnalyzedFixture:
    fixture: Fixture | None
    novibet_match: NovibetMatch
    probabilities: object | None
    fair_markets: list[dict]
    value_bets: list[ValueBet] = field(default_factory=list)
    odds: MarketOdds | None = None
    odds_source: str = "model-only"
    stats_available: bool = True


MANUAL_PROB_MAP = {
    "home_win": ("1X2", "Home Win"),
    "draw": ("1X2", "Draw"),
    "away_win": ("1X2", "Away Win"),
    "over_25": ("Over/Under", "Over 2.5"),
    "under_25": ("Over/Under", "Under 2.5"),
    "btts_yes": ("BTTS", "Yes"),
    "btts_no": ("BTTS", "No"),
    "dc_1x": ("Double Chance", "1X"),
    "dc_x2": ("Double Chance", "X2"),
    "dc_12": ("Double Chance", "12"),
}


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


def _find_fotmob_fixture(novibet_match: NovibetMatch, index: list[Fixture]) -> Fixture | None:
    for fixture in index:
        if teams_match(novibet_match.home, novibet_match.away, fixture.home_name, fixture.away_name):
            return fixture
    return None


def _evaluate_with_odds(
    odds: MarketOdds,
    probabilities: object | None,
    manual_probs: dict[str, float],
    config: ScanConfig,
) -> tuple[list[ValueBet], list[dict]]:
    value_bets: list[ValueBet] = []
    fair_markets: list[dict] = []

    if probabilities is not None:
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

    for odds_attr, (market, selection) in MANUAL_PROB_MAP.items():
        book_odds = getattr(odds, odds_attr, None)
        manual_prob = manual_probs.get(odds_attr)
        if book_odds is None or manual_prob is None:
            continue
        if manual_prob > 1:
            manual_prob = manual_prob / 100.0
        bet = evaluate_market(
            market=market,
            selection=selection,
            model_probability=manual_prob,
            odds=book_odds,
            min_odds=config.min_odds,
            max_odds=config.max_odds,
            min_value_pct=config.min_value_pct,
        )
        if bet:
            value_bets.append(bet)

    value_bets.sort(key=lambda item: item.value_pct, reverse=True)
    return value_bets, fair_markets


def analyze_novibet_match(
    novibet_match: NovibetMatch,
    fixture: Fixture | None,
    config: ScanConfig,
) -> AnalyzedFixture | None:
    probabilities = None
    stats_available = False
    enriched: Fixture | None = None

    if fixture and novibet_match.sport in {"football", "soccer", ""}:
        enriched = enrich_fixture(fixture, config.form_limit)
        if (
            enriched.home_form.matches_used >= config.min_form_matches
            and enriched.away_form.matches_used >= config.min_form_matches
        ):
            lambda_home, lambda_away = estimate_lambdas(
                enriched.home_form.scored,
                enriched.home_form.conceded,
                enriched.away_form.scored,
                enriched.away_form.conceded,
            )
            probabilities = calculate_probabilities(lambda_home, lambda_away)
            stats_available = True

    odds = novibet_match.odds
    if not any(
        getattr(odds, field_name)
        for field_name in MarketOdds.__dataclass_fields__
        if field_name != "source"
    ):
        return None

    value_bets, fair_markets = _evaluate_with_odds(
        odds,
        probabilities,
        novibet_match.model_probability,
        config,
    )

    return AnalyzedFixture(
        fixture=enriched,
        novibet_match=novibet_match,
        probabilities=probabilities,
        fair_markets=fair_markets,
        value_bets=value_bets,
        odds=odds,
        odds_source=novibet_match.source,
        stats_available=stats_available,
    )


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
        return None

    novibet_match = NovibetMatch(
        home=fixture.home_name,
        away=fixture.away_name,
        sport="football",
        league=fixture.league,
        odds=odds,
        source=odds.source,
    )

    value_bets, fair_markets = _evaluate_with_odds(odds, probabilities, {}, config)

    return AnalyzedFixture(
        fixture=fixture,
        novibet_match=novibet_match,
        probabilities=probabilities,
        fair_markets=fair_markets,
        value_bets=value_bets,
        odds=odds,
        odds_source=odds.source,
        stats_available=True,
    )


def load_novibet_matches(novibet_config: Path) -> list[NovibetMatch]:
    manual = load_novibet_config(novibet_config)
    api = fetch_novibet_from_odds_api()
    return merge_novibet_sources(manual, api)


def scan_novibet(
    scan_date: date | None = None,
    config: ScanConfig | None = None,
    novibet_config: Path | None = None,
) -> list[AnalyzedFixture]:
    config = config or ScanConfig()
    scan_date = scan_date or date.today()
    novibet_config = novibet_config or Path("config/novibet.yaml")

    novibet_matches = load_novibet_matches(novibet_config)
    if not novibet_matches:
        return []

    index = fetch_fixture_index_for_dates(
        scan_date,
        days=config.scan_days,
        major_only=config.major_only,
    )

    results: list[AnalyzedFixture] = []
    for novibet_match in novibet_matches:
        fixture = _find_fotmob_fixture(novibet_match, index)
        analyzed = analyze_novibet_match(novibet_match, fixture, config)
        if analyzed:
            results.append(analyzed)

    return results


def scan(
    scan_date: date | None = None,
    config: ScanConfig | None = None,
    manual_odds: dict[str, dict] | None = None,
    novibet_config: Path | None = None,
) -> list[AnalyzedFixture]:
    config = config or ScanConfig()
    scan_date = scan_date or date.today()

    if config.novibet_only:
        return scan_novibet(scan_date, config, novibet_config)

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
