#!/usr/bin/env python3
"""Backtest mean-reversion candidates vs buy&hold."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yfinance as yf

from mean_reversion import (
    _flat,
    buy_hold_r,
    run_bollinger_mr,
    run_rsi2,
    summarize,
    to_utc,
    trades_frame,
    yearly_r,
)

OUT = Path(__file__).resolve().parent / "results"
OUT.mkdir(parents=True, exist_ok=True)


def load(symbol: str, period: str = "7y") -> pd.DataFrame:
    df = yf.download(symbol, period=period, interval="1d", progress=False, auto_adjust=True)
    return to_utc(_flat(df)[["Open", "High", "Low", "Close"]].dropna())


def window_start(df: pd.DataFrame, years: float = 5.0) -> pd.Timestamp:
    return df.index.max() - pd.Timedelta(days=int(365.25 * years))


def fmt(name, stats, bh, start, end, years=None) -> str:
    edge = stats["total_r"] - bh["bh_r"]
    lines = [
        f"### {name}",
        f"- Period: {start.date()} → {end.date()}",
        f"- Trades: {stats['trades']} (L {stats['longs']} / S {stats['shorts']})",
        f"- Win rate: {stats['win_rate']:.1f}% ({stats['wins']}W / {stats['losses']}L)",
        (
            f"- Strategy: {stats['total_r']:+.2f}R | avg {stats['avg_r']:+.3f}R | "
            f"PF {stats['profit_factor']:.2f} | DD {stats['max_dd_r']:.2f}R | bars {stats['avg_bars']:.1f}"
        ),
        f"- Buy&Hold: {bh['bh_pct']:+.1f}% ≈ {bh['bh_r']:+.2f}R",
        f"- Strategy − B&H: {edge:+.2f}R",
    ]
    if years:
        lines.append("- Yearly R: " + ", ".join(f"{y}:{v:+.1f}" for y, v in years.items()))
    lines.append("")
    return "\n".join(lines)


def finalize(label, symbol, trades, start, extra=None):
    trades = [t for t in trades if t.entry_time >= start]
    stats = summarize(trades)
    w = trades  # noqa
    # window from data via trade list / start
    bh = None
    return trades, stats


def run_case(label, symbol, df, start, trades, cost_note=""):
    trades = [t for t in trades if t.entry_time >= start]
    stats = summarize(trades)
    w = df[df.index >= start]
    bh = buy_hold_r(df, start)
    y = yearly_r(trades)
    years = {int(k): float(v) for k, v in y.items()} if len(y) else {}
    print(fmt(label, stats, bh, w.index.min(), w.index.max(), years))
    safe = label.replace(" ", "_").replace("/", "_").replace("&", "and").replace("−", "-")
    trades_frame(trades).to_csv(OUT / f"{safe}_trades.csv", index=False)
    (OUT / f"{safe}_stats.json").write_text(
        json.dumps(
            {
                "label": label,
                "symbol": symbol,
                "start": str(w.index.min()),
                "end": str(w.index.max()),
                "buy_hold": bh,
                "yearly_r": years,
                **stats,
            },
            indent=2,
            default=str,
        )
    )
    return label, stats, bh, w.index.min(), w.index.max(), years


def main():
    cases = []
    md = [
        "# Mean-Reversion Candidates vs Buy&Hold",
        "",
        "Goal: find rules that are **not just riding a bull**.",
        "",
        "## Strategies",
        "1. **RSI(2) dip-buy** (Connors-style): RSI2≤10 & Close>SMA200 → buy next open; exit RSI2≥70; SL 2×ATR",
        "2. **Bollinger fade**: fade BB(20,2) to mid; optional ADX<25; SL 2×ATR; long/short",
        "",
        "## Results",
        "",
    ]

    # RSI2 indices / gold
    for symbol, name, cost in [("NQ=F", "US100/NQ", 3.0), ("^GSPC", "SPX", 1.0), ("GC=F", "Gold", 3.0)]:
        print(f"RSI2 {symbol}...")
        df = load(symbol, "7y")
        start = window_start(df, 5)
        for buy in (10, 5):
            trades, _ = run_rsi2(
                df,
                rsi_buy=buy,
                rsi_exit=70,
                trend_sma=200,
                cost_bps_rt=cost,
                mode="long_only",
            )
            cases.append(run_case(f"{name} RSI2≤{buy} dip-buy 5y", symbol, df, start, trades))

    # Bollinger FX 5y
    for symbol, name, cost in [
        ("EURUSD=X", "EURUSD", 1.5),
        ("GBPUSD=X", "GBPUSD", 1.5),
        ("USDJPY=X", "USDJPY", 1.5),
        ("AUDUSD=X", "AUDUSD", 1.5),
    ]:
        print(f"BB {symbol}...")
        df = load(symbol, "7y")
        start = window_start(df, 5)
        for use_adx, tag in ((True, "+ADX"), (False, "noADX")):
            trades, _ = run_bollinger_mr(
                df,
                use_adx_filter=use_adx,
                adx_max=25,
                cost_bps_rt=cost,
                mode="long_short",
            )
            cases.append(run_case(f"{name} BB fade {tag} 5y", symbol, df, start, trades))

    # EURUSD longer history
    print("BB EURUSD max...")
    eurusd = load("EURUSD=X", "max")
    start_all = eurusd.index.min() + pd.Timedelta(days=400)
    for use_adx, tag in ((True, "+ADX"), (False, "noADX")):
        trades, _ = run_bollinger_mr(
            eurusd,
            use_adx_filter=use_adx,
            adx_max=25,
            cost_bps_rt=1.5,
            mode="long_short",
        )
        cases.append(run_case(f"EURUSD BB fade {tag} MAX", "EURUSD=X", eurusd, start_all, trades))

    for item in cases:
        md.append(fmt(*item))

    # Pick winners automatically for the report footer
    md.append("## Auto-screen (this run)")
    scored = []
    for label, stats, bh, start, end, years in cases:
        edge = stats["total_r"] - bh["bh_r"]
        fx = "EURUSD" in label or "GBPUSD" in label or "USDJPY" in label or "AUDUSD" in label
        ok = False
        reason = ""
        if fx:
            ok = stats["total_r"] > 5 and stats["profit_factor"] >= 1.3 and stats["trades"] >= 30
            reason = "FX absolute edge"
        else:
            ok = edge > 0 and stats["total_r"] > 0 and stats["profit_factor"] >= 1.2
            reason = "beats B&H"
        scored.append((ok, edge, stats["total_r"], label, reason))

    winners = [s for s in scored if s[0]]
    if winners:
        md.append("Candidates that cleared the bar:")
        for ok, edge, total, label, reason in winners:
            md.append(f"- **{label}** ({reason}: total {total:+.1f}R, edge vs B&H {edge:+.1f}R)")
    else:
        md.append(
            "No candidate fully cleared the bar. Closest by total R / edge listed below — treat as research only."
        )
        closest = sorted(scored, key=lambda x: (x[2], x[1]), reverse=True)[:5]
        for ok, edge, total, label, reason in closest:
            md.append(f"- {label}: total {total:+.1f}R, vs B&H {edge:+.1f}R")

    md += ["", "Not financial advice.", ""]
    text = "\n".join(md)
    (OUT / "MEANREV_REPORT.md").write_text(text)
    print("=" * 60)
    print(text)


if __name__ == "__main__":
    main()
