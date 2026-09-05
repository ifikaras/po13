#!/usr/bin/env python3
"""Download data and run CRT backtests. Prints a results report."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yfinance as yf

from strategy import _flatten_columns, run_crt_backtest, to_utc_index, trades_to_frame


OUT = Path(__file__).resolve().parent / "results"
OUT.mkdir(parents=True, exist_ok=True)


def download(symbol: str, interval: str, period: str) -> pd.DataFrame:
    df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
    df = _flatten_columns(df)
    if df.empty:
        raise RuntimeError(f"No data for {symbol} {interval} {period}")
    df = df.rename(columns=str.title) if "Open" not in df.columns else df
    # yfinance already uses Open/High/Low/Close
    cols = [c for c in ["Open", "High", "Low", "Close"] if c in df.columns]
    df = df[cols].dropna()
    return to_utc_index(df)


def fmt_stats(name: str, stats: dict, start, end) -> str:
    lines = [
        f"### {name}",
        f"- Period: {start} → {end}",
        f"- Trades: {stats['trades']} (L {stats['longs']} / S {stats['shorts']})",
        f"- Win rate: {stats['win_rate']:.1f}% ({stats['wins']}W / {stats['losses']}L)",
        f"- Total R: {stats['total_r']:+.2f}R",
        f"- Avg R / trade: {stats['avg_r']:+.3f}R",
        f"- Profit factor: {stats['profit_factor']:.2f}",
        f"- Max DD: {stats['max_dd_r']:.2f}R",
        f"- Best / Worst: {stats['best_r']:+.2f}R / {stats['worst_r']:+.2f}R",
        "",
    ]
    return "\n".join(lines)


def run_case(label: str, symbol: str, interval: str, period: str, **kwargs):
    print(f"Downloading {symbol} {interval} {period}...")
    df = download(symbol, interval, period)
    trades, stats = run_crt_backtest(df, **kwargs)
    start = df.index.min()
    end = df.index.max()
    print(fmt_stats(label, stats, start, end))
    safe = label.replace(" ", "_").replace("/", "_").replace("+", "plus")
    trades_to_frame(trades).to_csv(OUT / f"{safe}_trades.csv", index=False)
    with open(OUT / f"{safe}_stats.json", "w") as f:
        json.dump(
            {
                "label": label,
                "symbol": symbol,
                "interval": interval,
                "period": period,
                "start": str(start),
                "end": str(end),
                **stats,
            },
            f,
            indent=2,
        )
    return label, stats, start, end, len(trades)


def main():
    report = []
    cases = []

    # Exact strategy: H4 CRT + M15 entry (yfinance ~60d limit for 15m)
    for symbol, name in [("NQ=F", "US100/NQ"), ("EURUSD=X", "EURUSD")]:
        cases.append(
            run_case(
                f"{name} H4+M15 strict (60d)",
                symbol,
                "15m",
                "60d",
                range_rule="4h",
                require_color_confirm=True,
                use_session_filter=True,
                partial_at_mid=True,
                min_rr=1.5,
            )
        )

    # Longer history proxy: H4 CRT + H1 entry (~2y)
    for symbol, name in [("NQ=F", "US100/NQ"), ("EURUSD=X", "EURUSD")]:
        cases.append(
            run_case(
                f"{name} H4+H1 proxy (2y)",
                symbol,
                "1h",
                "2y",
                range_rule="4h",
                require_color_confirm=True,
                use_session_filter=True,
                partial_at_mid=True,
                min_rr=1.5,
            )
        )

    # Ablation: without color confirm (wick sweep only + close inside)
    cases.append(
        run_case(
            "US100/NQ H4+H1 NO color confirm (2y)",
            "NQ=F",
            "1h",
            "2y",
            range_rule="4h",
            require_color_confirm=False,
            use_session_filter=True,
            partial_at_mid=True,
            min_rr=1.5,
        )
    )

    # Ablation: no session filter
    cases.append(
        run_case(
            "US100/NQ H4+H1 no session filter (2y)",
            "NQ=F",
            "1h",
            "2y",
            range_rule="4h",
            require_color_confirm=True,
            use_session_filter=False,
            partial_at_mid=True,
            min_rr=1.5,
        )
    )

    md = [
        "# CRT Strategy Backtest Results",
        "",
        "## Rules tested",
        "- CRT range = previous closed **H4** candle",
        "- Entry on **M15** (exact) or **H1** (long-history proxy)",
        "- Sweep high/low → close back inside range → candle color confirm",
        "- SL beyond sweep + 0.1×ATR(H4)",
        "- TP1 = mid (50%, BE on remainder), TP2 = opposite side",
        "- Min RR to TP2 = 1.5, max SL = 3×ATR, 1 trade per CRT range",
        "- Session 07:00–21:00 UTC (unless noted)",
        "- Same-bar SL/TP conflict counted as **SL** (conservative)",
        "- Data: Yahoo Finance (`NQ=F`, `EURUSD=X`)",
        "",
        "## Results",
        "",
    ]
    for label, stats, start, end, _n in cases:
        md.append(fmt_stats(label, stats, start, end))

    md.append("## Notes")
    md.append("- M15 history is limited by Yahoo (~60 days); H1 proxy covers ~2 years.")
    md.append("- This is CFD/futures proxy data, not broker MT5 ticks — spreads/slippage not modeled.")
    md.append("- Not financial advice; educational backtest only.")
    md.append("")

    text = "\n".join(md)
    (OUT / "REPORT.md").write_text(text)
    print("=" * 60)
    print(text)


if __name__ == "__main__":
    main()
