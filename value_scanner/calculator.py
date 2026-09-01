"""Value bet calculations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValueBet:
    market: str
    selection: str
    odds: float
    model_probability: float
    implied_probability: float
    value_pct: float
    fair_odds: float


def implied_probability(odds: float) -> float:
    return 1.0 / odds


def value_percentage(model_probability: float, odds: float) -> float:
    return (model_probability * odds - 1.0) * 100.0


def evaluate_market(
    market: str,
    selection: str,
    model_probability: float,
    odds: float,
    min_odds: float,
    max_odds: float | None,
    min_value_pct: float,
    market_probability: float | None = None,
    market_odds_full: list[float] | None = None,
    selection_index: int = 0,
) -> ValueBet | None:
    from value_scanner.market_anchor import evaluate_anchored_edge
    from value_scanner.professional import required_edge_pct

    if odds < min_odds:
        return None
    if max_odds is not None and odds > max_odds:
        return None

    threshold = max(min_value_pct, required_edge_pct(odds))
    should_play, value_pct, anchor, _reason = evaluate_anchored_edge(
        model_probability,
        odds,
        market=market,
        market_probability=market_probability,
        market_odds_full=market_odds_full,
        selection_index=selection_index,
        min_edge_pct=threshold,
    )
    if not should_play:
        return None

    return ValueBet(
        market=market,
        selection=selection,
        odds=round(odds, 2),
        model_probability=round(anchor.anchored_probability * 100, 1),
        implied_probability=round(implied_probability(odds) * 100, 1),
        value_pct=round(value_pct, 1),
        fair_odds=anchor.fair_odds,
    )
