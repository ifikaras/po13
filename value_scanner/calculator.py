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
) -> ValueBet | None:
    from value_scanner.professional import required_edge_pct

    if odds < min_odds:
        return None
    if max_odds is not None and odds > max_odds:
        return None

    value_pct = value_percentage(model_probability, odds)
    threshold = max(min_value_pct, required_edge_pct(odds))
    if value_pct < threshold:
        return None

    return ValueBet(
        market=market,
        selection=selection,
        odds=round(odds, 2),
        model_probability=round(model_probability * 100, 1),
        implied_probability=round(implied_probability(odds) * 100, 1),
        value_pct=round(value_pct, 1),
        fair_odds=round(1.0 / model_probability, 2) if model_probability > 0 else 0.0,
    )
