#!/usr/bin/env python3
"""Daily-only CRT backtest over multi-year history."""

from __future__ import annotations

import json
from pathlib import Path

from run_backtest import download, fmt_stats, OUT
from strategy import run_crt_backtest, trades_to_frame


def run_case(label: str, symbol: str, period: str, **kwargs):
    print(f"Downloading {symbol} 1d {period}...")
    df = download(symbol, "1d", period)
    trades, stats = run_crt_backtest(df, range_rule="1D", use_session_filter=False, **kwargs)
    start, end = df.index.min(), df.index.max()
    print(fmt_stats(label, stats, start, end))
    safe = label.replace(" ", "_").replace("/", "_").replace("+", "plus")
    trades_to_frame(trades).to_csv(OUT / f"{safe}_trades.csv", index=False)
    payload = {
        "label": label,
        "symbol": symbol,
        "interval": "1d",
        "period": period,
        "start": str(start),
        "end": str(end),
        **stats,
    }
    (OUT / f"{safe}_stats.json").write_text(json.dumps(payload, indent=2))
    return label, stats, start, end


def main():
    cases = []
    symbols = [("NQ=F", "US100/NQ"), ("EURUSD=X", "EURUSD")]

    for period in ("4y", "5y"):
        for symbol, name in symbols:
            cases.append(
                run_case(
                    f"{name} D1 strict ({period})",
                    symbol,
                    period,
                    require_color_confirm=True,
                    partial_at_mid=True,
                    min_rr=1.5,
                    max_sl_atr=3.0,
                )
            )

    # Ablations on 4y US100
    cases.append(
        run_case(
            "US100/NQ D1 NO color confirm (4y)",
            "NQ=F",
            "4y",
            require_color_confirm=False,
            partial_at_mid=True,
            min_rr=1.5,
        )
    )
    cases.append(
        run_case(
            "US100/NQ D1 minRR=1.0 (4y)",
            "NQ=F",
            "4y",
            require_color_confirm=True,
            partial_at_mid=True,
            min_rr=1.0,
        )
    )
    cases.append(
        run_case(
            "EURUSD D1 minRR=1.0 (4y)",
            "EURUSD=X",
            "4y",
            require_color_confirm=True,
            partial_at_mid=True,
            min_rr=1.0,
        )
    )

    md = [
        "# CRT Daily-Only Backtest (3–5 years)",
        "",
        "## Rules",
        "- CRT range = **previous closed Daily candle**",
        "- Entry = same Daily TF (sweep + close back inside + color confirm)",
        "- No session filter (not meaningful on D1)",
        "- SL beyond sweep + 0.1×ATR(D1); TP1 mid / TP2 opposite side",
        "- Default min RR to TP2 = 1.5 (plus looser RR=1.0 ablation)",
        "- Data: Yahoo Finance daily (`NQ=F`, `EURUSD=X`)",
        "",
        "## Results",
        "",
    ]
    for label, stats, start, end in cases:
        md.append(fmt_stats(label, stats, start, end))

    md += [
        "## Interpretation notes",
        "- D1 CRT produces far fewer trades than H4/M15.",
        "- Same-bar SL/TP conflicts counted as SL (conservative).",
        "- No spread/slippage; not broker MT5 data.",
        "- Not financial advice.",
        "",
    ]
    text = "\n".join(md)
    (OUT / "DAILY_REPORT.md").write_text(text)
    print("=" * 60)
    print(text)


if __name__ == "__main__":
    main()
