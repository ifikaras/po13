"""Professional value-betting thresholds (edge by odds tier, not hard odds caps).

Works with value_scanner.market_anchor — bookmaker-style fusion of model + market.
"""

from __future__ import annotations

# Floor: heavy favorites rarely offer durable edge after vig.
MIN_ODDS = 1.40

# Soft preference band for daily-pick scoring (not a play/skip gate).
PREFERRED_ODDS_MIN = 1.70
PREFERRED_ODDS_MAX = 2.50

# Minimum *anchored* edge (EV %) required to PLAY, scaled by offered odds.
# Based on industry practice: ~3% main lines, higher for longshots/variance.
EDGE_TIERS: tuple[tuple[float, float, float], ...] = (
    (1.40, 2.50, 3.0),   # sweet spot — sides, totals, DC in liquid leagues
    (2.50, 4.00, 5.0),   # higher variance — need stronger confirmed edge
    (4.00, 15.0, 8.0),   # longshots — only with large, verified mispricing
)

# Market-anchor caps live in value_scanner.market_anchor (avoid circular import).


def required_edge_pct(odds: float) -> float:
    """Return minimum +EV % needed to recommend PLAY at these odds."""
    for low, high, edge in EDGE_TIERS:
        if low <= odds < high:
            return edge
    return EDGE_TIERS[-1][2]


def odds_in_preferred_band(odds: float) -> bool:
    return PREFERRED_ODDS_MIN <= odds <= PREFERRED_ODDS_MAX


def pick_preference_bonus(odds: float) -> float:
    """Small scoring boost for picks in the stable mid-range band."""
    if odds_in_preferred_band(odds):
        return 0.02
    if odds < PREFERRED_ODDS_MIN:
        return -0.01
    if odds <= 4.0:
        return 0.0
    return -0.02
