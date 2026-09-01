"""Fuzzy team name matching for cross-source fixture lookup."""

from __future__ import annotations


def normalize_name(name: str) -> str:
    return "".join(ch.lower() for ch in name if ch.isalnum())


def _tokens(name: str) -> set[str]:
    raw = name.lower()
    for sep in [" - ", " vs ", "/", "&"]:
        raw = raw.replace(sep, " ")
    return {p for p in raw.split() if len(p) > 2}


def name_similarity(left: str, right: str) -> float:
    left_norm = normalize_name(left)
    right_norm = normalize_name(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    if left_norm in right_norm or right_norm in left_norm:
        return 0.92

    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0

    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return overlap / union


def teams_match(home_a: str, away_a: str, home_b: str, away_b: str, threshold: float = 0.55) -> bool:
    direct = (
        name_similarity(home_a, home_b) >= threshold
        and name_similarity(away_a, away_b) >= threshold
    )
    swapped = (
        name_similarity(home_a, away_b) >= threshold
        and name_similarity(away_a, home_b) >= threshold
    )
    return direct or swapped
