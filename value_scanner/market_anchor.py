"""Market-anchor engine — bookmaker-grade probability fusion.

How a sharp desk prices (and how we decide PLAY/SKIP):

1. Independent model (Poisson / form) produces p_model.
2. If we have a *sharp* / consensus market (full board), de-vig → p_market,
   then shrink p_model toward p_market (Bayesian board update).
3. The soft book we bet (Novibet) is the *offer*, not the truth.
   Comparing soft implied to our fair price is how we measure edge.
4. Soft-only sanity: never blend toward the same soft price we are betting
   (that would erase real soft-book value). Instead:
   - Reject if model vs soft-implied divergence is absurd (model bug).
   - Cap raw model EV at a believable ceiling without sharp confirm.
5. Only PLAY when anchored (or model-under-sanity) EV clears tier thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# --- Bookmaker risk parameters -------------------------------------------------

# Trust in form-Poisson vs sharp market when they mostly agree.
BASE_MODEL_WEIGHT = 0.35

# Absolute probability gap (fraction) vs sharp market → full defer to market.
MAX_MARKET_DIVERGENCE = 0.12  # 12pp

# Soft-only: if model and soft-implied disagree by more than this → model bug.
# Softer than sharp divergence: soft books are supposed to be wrong sometimes.
MAX_SOFT_DIVERGENCE = 0.18  # 18pp

# Soft-only: raw model EV above this without sharp confirm → reject.
MAX_UNANCHORED_EDGE_PCT = 12.0

# Absolute ceiling even with sharp support (soft books rarely leave more).
MAX_BELIEVABLE_EDGE_PCT = 15.0

# Typical overrounds (documentation / full-board helpers).
TWO_WAY_OVERROUND = 0.05
THREE_WAY_OVERROUND = 0.07
DC_OVERROUND = 0.04


class AnchorStatus(str, Enum):
    SHARP_ANCHORED = "sharp_anchored"
    SOFT_SANITY = "soft_sanity"
    MODEL_ONLY = "model_only"
    REJECTED_DIVERGENCE = "rejected_divergence"
    REJECTED_EDGE_CAP = "rejected_edge_cap"


@dataclass(frozen=True)
class AnchorResult:
    model_probability: float
    market_probability: float | None
    anchored_probability: float
    model_weight: float
    divergence_pp: float
    status: AnchorStatus
    note: str

    @property
    def fair_odds(self) -> float:
        p = self.anchored_probability
        return round(1.0 / p, 2) if p > 0 else 0.0


def multiplicative_devig(odds_list: list[float]) -> list[float]:
    """Remove overround proportionally → fair probabilities that sum to 1."""
    implied = [1.0 / o for o in odds_list if o and o > 1.0]
    if not implied:
        return []
    total = sum(implied)
    if total <= 0:
        return []
    return [p / total for p in implied]


def blend_with_sharp(
    model_p: float,
    sharp_p: float,
    *,
    base_model_weight: float = BASE_MODEL_WEIGHT,
    max_divergence: float = MAX_MARKET_DIVERGENCE,
) -> AnchorResult:
    """Shrink model toward a sharp/consensus fair line (board update)."""
    model_p = _clamp_prob(model_p)
    sharp_p = _clamp_prob(sharp_p)
    divergence = abs(model_p - sharp_p)

    if divergence >= max_divergence:
        return AnchorResult(
            model_probability=model_p,
            market_probability=sharp_p,
            anchored_probability=sharp_p,
            model_weight=0.0,
            divergence_pp=divergence,
            status=AnchorStatus.REJECTED_DIVERGENCE,
            note=(
                f"Μοντέλο vs sharp διαφέρουν {divergence * 100:.1f}pp "
                f"(όριο {max_divergence * 100:.0f}pp) → εμπιστοσύνη στην αγορά."
            ),
        )

    confidence = 1.0 - (divergence / max_divergence)
    weight = base_model_weight * confidence
    anchored = weight * model_p + (1.0 - weight) * sharp_p
    return AnchorResult(
        model_probability=model_p,
        market_probability=sharp_p,
        anchored_probability=_clamp_prob(anchored),
        model_weight=weight,
        divergence_pp=divergence,
        status=AnchorStatus.SHARP_ANCHORED,
        note=(
            f"Sharp blend: μοντέλο {weight * 100:.0f}% / αγορά {(1 - weight) * 100:.0f}% "
            f"(απόκλιση {divergence * 100:.1f}pp)."
        ),
    )


def soft_sanity_check(
    model_p: float,
    offered_odds: float,
    *,
    max_soft_divergence: float = MAX_SOFT_DIVERGENCE,
    max_unanchored_edge: float = MAX_UNANCHORED_EDGE_PCT,
) -> AnchorResult:
    """Sanity-check model against the soft offer without erasing soft value.

    Soft implied (1/odds) includes vig, so model > soft_implied is normal for
    +EV. We only reject when the gap is so large it cannot be vig — it must
    be model failure (e.g. model 66% vs soft 22%).

    When raw EV exceeds the soft-only ceiling but divergence is still
    believable, we *cap* fair probability so EV equals the ceiling — the
    bookmaker posts a conservative line, not a fantasy edge.
    """
    from value_scanner.calculator import value_percentage

    model_p = _clamp_prob(model_p)
    soft_implied = 1.0 / offered_odds if offered_odds > 1.0 else 0.5
    divergence = abs(model_p - soft_implied)
    raw_ev = value_percentage(model_p, offered_odds)

    if divergence >= max_soft_divergence:
        return AnchorResult(
            model_probability=model_p,
            market_probability=soft_implied,
            anchored_probability=soft_implied,
            model_weight=0.0,
            divergence_pp=divergence,
            status=AnchorStatus.REJECTED_DIVERGENCE,
            note=(
                f"Μοντέλο {model_p * 100:.1f}% vs soft implied {soft_implied * 100:.1f}% "
                f"= {divergence * 100:.1f}pp (όριο {max_soft_divergence * 100:.0f}pp) → model bug."
            ),
        )

    if raw_ev > max_unanchored_edge:
        # Cap fair p so EV == max_unanchored_edge (conservative board).
        p_capped = (1.0 + max_unanchored_edge / 100.0) / offered_odds
        p_capped = _clamp_prob(p_capped)
        # Only accept cap if it sits between soft implied and model (shrink).
        low, high = sorted((soft_implied, model_p))
        if low <= p_capped <= high or abs(p_capped - model_p) < abs(soft_implied - model_p):
            p_capped = min(max(p_capped, low), high)
            return AnchorResult(
                model_probability=model_p,
                market_probability=soft_implied,
                anchored_probability=p_capped,
                model_weight=p_capped / model_p if model_p else 0.0,
                divergence_pp=divergence,
                status=AnchorStatus.SOFT_SANITY,
                note=(
                    f"Soft edge capped at +{max_unanchored_edge:.0f}% "
                    f"(raw model was +{raw_ev:.1f}%; fair {p_capped * 100:.1f}%)."
                ),
            )
        return AnchorResult(
            model_probability=model_p,
            market_probability=soft_implied,
            anchored_probability=model_p,
            model_weight=1.0,
            divergence_pp=divergence,
            status=AnchorStatus.REJECTED_EDGE_CAP,
            note=(
                f"Raw model EV +{raw_ev:.1f}% πάνω από soft-only cap "
                f"+{max_unanchored_edge:.0f}% χωρίς sharp confirm."
            ),
        )

    return AnchorResult(
        model_probability=model_p,
        market_probability=soft_implied,
        anchored_probability=model_p,
        model_weight=1.0,
        divergence_pp=divergence,
        status=AnchorStatus.SOFT_SANITY,
        note=(
            f"Soft sanity OK: μοντέλο {model_p * 100:.1f}% vs soft implied "
            f"{soft_implied * 100:.1f}% (gap {divergence * 100:.1f}pp, EV +{raw_ev:.1f}%)."
        ),
    )


def evaluate_anchored_edge(
    model_probability: float,
    offered_odds: float,
    *,
    market: str = "",
    market_probability: float | None = None,
    market_odds_full: list[float] | None = None,
    selection_index: int = 0,
    min_edge_pct: float | None = None,
    max_unanchored_edge: float = MAX_UNANCHORED_EDGE_PCT,
    max_believable_edge: float = MAX_BELIEVABLE_EDGE_PCT,
) -> tuple[bool, float, AnchorResult, str]:
    """Return (should_play, value_pct, anchor, reason)."""
    from value_scanner.calculator import value_percentage
    from value_scanner.professional import required_edge_pct

    model_probability = _clamp_prob(model_probability)
    threshold = min_edge_pct if min_edge_pct is not None else required_edge_pct(offered_odds)

    # Resolve sharp/consensus fair if full board provided.
    sharp_p = market_probability
    if market_odds_full and sharp_p is None:
        fair_probs = multiplicative_devig(market_odds_full)
        if fair_probs and 0 <= selection_index < len(fair_probs):
            sharp_p = fair_probs[selection_index]

    if sharp_p is not None:
        anchor = blend_with_sharp(model_probability, sharp_p)
    else:
        anchor = soft_sanity_check(
            model_probability,
            offered_odds,
            max_unanchored_edge=max_unanchored_edge,
        )

    anchored_ev = value_percentage(anchor.anchored_probability, offered_odds)
    raw_ev = value_percentage(model_probability, offered_odds)

    if anchor.status == AnchorStatus.REJECTED_DIVERGENCE:
        return (
            False,
            round(anchored_ev, 1),
            anchor,
            f"SKIP — model/market conflict. {anchor.note}",
        )

    if anchor.status == AnchorStatus.REJECTED_EDGE_CAP:
        return (
            False,
            round(raw_ev, 1),
            anchor,
            f"SKIP — {anchor.note}",
        )

    if anchored_ev > max_believable_edge:
        return (
            False,
            round(anchored_ev, 1),
            AnchorResult(
                model_probability=anchor.model_probability,
                market_probability=anchor.market_probability,
                anchored_probability=anchor.anchored_probability,
                model_weight=anchor.model_weight,
                divergence_pp=anchor.divergence_pp,
                status=AnchorStatus.REJECTED_EDGE_CAP,
                note=f"Anchored EV +{anchored_ev:.1f}% > believable +{max_believable_edge:.0f}%.",
            ),
            f"SKIP — anchored edge +{anchored_ev:.1f}% πάνω από believable +{max_believable_edge:.0f}%.",
        )

    if anchored_ev >= threshold:
        return (
            True,
            round(anchored_ev, 1),
            anchor,
            (
                f"ΠΑΙΞΕ — anchored value +{anchored_ev:.1f}% "
                f"(μοντέλο {model_probability * 100:.1f}% → "
                f"fair {anchor.anchored_probability * 100:.1f}% × {offered_odds}, "
                f"όριο +{threshold:.0f}%)."
            ),
        )

    return (
        False,
        round(anchored_ev, 1),
        anchor,
        (
            f"SKIP — anchored value {anchored_ev:+.1f}% "
            f"(χρειάζεται ≥ +{threshold:.0f}%). {anchor.note}"
        ),
    )


def _clamp_prob(p: float) -> float:
    return max(0.01, min(0.99, float(p)))
