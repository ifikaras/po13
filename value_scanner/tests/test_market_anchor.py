"""Self-check market-anchor like a bookmaker desk."""

from __future__ import annotations

from value_scanner.market_anchor import evaluate_anchored_edge, multiplicative_devig


def main() -> int:
    cases = [
        ("Sassuolo BTTS No @2.03", 0.535, 2.03, "BTTS", None, None, 0, True),
        ("Liverpool X2 @2.35", 0.562, 2.35, "Double Chance", None, None, 0, True),
        ("Espanyol away @4.42", 0.658, 4.42, "1X2", None, None, 0, False),
        ("Over 2.5 model 87.8% @1.88", 0.878, 1.88, "Over/Under", None, None, 0, False),
        ("Brest X2 @1.45", 0.715, 1.45, "Double Chance", None, None, 0, True),
        ("Bournemouth 1X @1.28", 0.681, 1.28, "Double Chance", None, None, 0, False),
        (
            "Espanyol with sharp 1X2",
            0.658,
            4.42,
            "1X2",
            None,
            [1.83, 3.80, 4.42],
            2,
            False,
        ),
    ]

    print(f"{'Case':38} {'Raw':>7} {'Anch':>7} {'Want':5} {'Got':5} OK?")
    failed = 0
    for name, p, odds, market, mp, full, idx, want_play in cases:
        play, val, anchor, _ = evaluate_anchored_edge(
            p,
            odds,
            market=market,
            market_probability=mp,
            market_odds_full=full,
            selection_index=idx,
        )
        raw = (p * odds - 1) * 100
        ok = play is want_play
        if not ok:
            failed += 1
        print(
            f"{name:38} {raw:+6.1f}% {val:+6.1f}% "
            f"{'PLAY' if want_play else 'SKIP':5} {'PLAY' if play else 'SKIP':5} "
            f"{'✓' if ok else '✗'} [{anchor.status.value}]"
        )

    fair = multiplicative_devig([1.83, 3.80, 4.42])
    assert abs(sum(fair) - 1.0) < 1e-9
    print(f"\nDevig 1X2 fair: {[round(x * 100, 1) for x in fair]}")
    print(f"\n{'PASS' if failed == 0 else f'FAIL ({failed})'}")
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
