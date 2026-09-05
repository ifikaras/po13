#!/usr/bin/env python3
"""Last 5y Donchian/ATR breakout + buy&hold comparison."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yfinance as yf

from breakout_strategy import _flat, prepare, run_breakout, summarize, trades_frame, yearly_r
from strategy import to_utc_index

OUT = Path(__file__).resolve().parent / "results"
OUT.mkdir(parents=True, exist_ok=True)

PARAMS = dict(
    entry_n=20,
    exit_n=10,
    atr_n=20,
    atr_stop=2.0,
    atr_trail=3.0,
    sma_n=200,
    use_sma_filter=True,
    use_donch_exit=True,
    use_atr_trail=True,
)


def load(symbol: str):
    df = yf.download(symbol, period="7y", interval="1d", progress=False, auto_adjust=True)
    df = to_utc_index(_flat(df)[["Open", "High", "Low", "Close"]].dropna())
    window_start = df.index.max() - pd.Timedelta(days=int(365.25 * 5))
    return df, window_start


def buy_hold(df: pd.DataFrame, window_start: pd.Timestamp) -> dict:
    prep = prepare(df, 20, 10, 20, 200)
    w = prep[prep.index >= window_start].dropna(subset=["atr", "Close"])
    entry = float(w.iloc[0]["Close"])
    exit_ = float(w.iloc[-1]["Close"])
    atr0 = float(w.iloc[0]["atr"])
    risk = 2.0 * atr0
    return {
        "bh_pct": (exit_ / entry - 1.0) * 100.0,
        "bh_r": (exit_ - entry) / risk if risk > 0 else 0.0,
        "start_px": entry,
        "end_px": exit_,
    }


def fmt(name, stats, bh, start, end, years) -> str:
    edge = stats["total_r"] - bh["bh_r"]
    lines = [
        f"### {name}",
        f"- Period: {start.date()} → {end.date()} (entries last 5y)",
        f"- Trades: {stats['trades']} (L {stats['longs']} / S {stats['shorts']})",
        f"- Win rate: {stats['win_rate']:.1f}% ({stats['wins']}W / {stats['losses']}L)",
        (
            f"- Strategy: {stats['total_r']:+.2f}R | avg {stats['avg_r']:+.3f}R | "
            f"PF {stats['profit_factor']:.2f} | DD {stats['max_dd_r']:.2f}R"
        ),
        f"- Buy&Hold: {bh['bh_pct']:+.1f}% ≈ {bh['bh_r']:+.2f}R (same 2×ATR unit)",
        f"- Strategy − B&H: {edge:+.2f}R",
    ]
    if years:
        lines.append("- Yearly R: " + ", ".join(f"{y}:{v:+.1f}" for y, v in years.items()))
    lines.append("")
    return "\n".join(lines)


def run_case(label, symbol, df, window_start, mode, cost):
    trades, _ = run_breakout(df, mode=mode, cost_bps_rt=cost, **PARAMS)
    trades = [t for t in trades if t.entry_time >= window_start]
    stats = summarize(trades)
    w = df[df.index >= window_start]
    start, end = w.index.min(), w.index.max()
    bh = buy_hold(df, window_start)
    y = yearly_r(trades)
    years = {int(k): float(v) for k, v in y.items()} if len(y) else {}
    print(fmt(label, stats, bh, start, end, years))
    safe = label.replace(" ", "_").replace("/", "_").replace("−", "-").replace("&", "and")
    trades_frame(trades).to_csv(OUT / f"{safe}_trades.csv", index=False)
    (OUT / f"{safe}_stats.json").write_text(
        json.dumps(
            {
                "label": label,
                "symbol": symbol,
                "mode": mode,
                "start": str(start),
                "end": str(end),
                "buy_hold": bh,
                "yearly_r": years,
                **stats,
            },
            indent=2,
            default=str,
        )
    )
    return label, stats, bh, start, end, years


def main():
    specs = [
        ("NQ=F", "US100/NQ", 3.0, True),
        ("GC=F", "Gold", 3.0, True),
        ("EURUSD=X", "EURUSD", 1.5, False),
        ("USDJPY=X", "USDJPY", 1.5, False),
        ("^GSPC", "SPX", 1.0, True),
    ]
    cases = []
    md = [
        "# Donchian/ATR Breakout — Last 5 Years + Buy&Hold",
        "",
        "Multi-decade NQ/Gold results are inflated by a secular bull.",
        "This run keeps **only entries in the last 5 years** and compares vs **buy&hold**",
        "in the same initial 2×ATR risk unit. FX is the cleaner stress test.",
        "",
        "## Results",
        "",
    ]
    for symbol, name, cost, also_long_only in specs:
        print(f"Downloading {symbol}...")
        df, window_start = load(symbol)
        cases.append(run_case(f"{name} 5y L/S", symbol, df, window_start, "long_short", cost))
        if also_long_only:
            cases.append(
                run_case(f"{name} 5y LONG-ONLY", symbol, df, window_start, "long_only", cost)
            )

    for item in cases:
        md.append(fmt(*item))

    md += [
        "## How to read Strategy − B&H",
        "- Near zero / negative on NQ or Gold long-only → bot mostly rides the bull you already get by holding.",
        "- FX weak too → little standalone edge in this window.",
        "",
        "Not financial advice. Yahoo daily OHLC + bps cost proxy.",
        "",
    ]
    text = "\n".join(md)
    (OUT / "BREAKOUT_5Y_REPORT.md").write_text(text)
    print("=" * 60)
    print(text)


if __name__ == "__main__":
    main()
