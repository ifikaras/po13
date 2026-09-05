#!/usr/bin/env python3
"""Backtest ORB on US100/NQ with Yahoo intraday + daily warmup."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yfinance as yf

from orb_strategy import _flat, run_orb, to_ny, trades_frame, yearly_r

OUT = Path(__file__).resolve().parent / "results"
OUT.mkdir(parents=True, exist_ok=True)

BASE = dict(
    use_daily_bias=True,
    sma_n=200,
    min_or_atr=0.10,
    max_or_atr=0.80,
    tp1_r=1.0,
    tp2_r=2.0,
    partial_at_tp1=True,
    flatten_at_close=True,
    cost_bps_rt=1.5,
)


def load(symbol: str, interval: str, period: str) -> pd.DataFrame:
    df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
    df = _flat(df)
    if df.empty:
        raise RuntimeError(f"No data {symbol} {interval} {period}")
    return df[["Open", "High", "Low", "Close"]].dropna()


def fmt(name, stats, start, end, years=None) -> str:
    lines = [
        f"### {name}",
        f"- Period: {pd.Timestamp(start).date()} → {pd.Timestamp(end).date()}",
        f"- Trades: {stats['trades']} (L {stats['longs']} / S {stats['shorts']})",
        f"- Win rate: {stats['win_rate']:.1f}% ({stats['wins']}W / {stats['losses']}L)",
        (
            f"- Total R: {stats['total_r']:+.2f}R | avg {stats['avg_r']:+.3f}R | "
            f"PF {stats['profit_factor']:.2f} | DD {stats['max_dd_r']:.2f}R"
        ),
        f"- Best / Worst: {stats['best_r']:+.2f}R / {stats['worst_r']:+.2f}R",
    ]
    if years:
        lines.append("- Yearly R: " + ", ".join(f"{y}:{v:+.1f}" for y, v in years.items()))
    lines.append("")
    return "\n".join(lines)


def run_case(label: str, df: pd.DataFrame, daily: pd.DataFrame, **kwargs):
    trades, stats = run_orb(df, daily_df=daily, **kwargs)
    ny = to_ny(df)
    start, end = ny.index.min(), ny.index.max()
    years = yearly_r(trades)
    print(fmt(label, stats, start, end, years))
    safe = (
        label.replace(" ", "_")
        .replace("/", "_")
        .replace("+", "plus")
        .replace("(", "")
        .replace(")", "")
    )
    trades_frame(trades).to_csv(OUT / f"{safe}_trades.csv", index=False)
    (OUT / f"{safe}_stats.json").write_text(
        json.dumps(
            {
                "label": label,
                "start": str(start),
                "end": str(end),
                "params": kwargs,
                "yearly_r": years,
                **stats,
            },
            indent=2,
            default=str,
        )
    )
    return label, stats, start, end, years


def main():
    print("Downloading NQ=F daily max (warmup for SMA200/ATR)...")
    daily = load("NQ=F", "1d", "max")

    cases = []
    md = [
        "# US100/NQ Opening Range Breakout Backtest",
        "",
        "## Rules",
        "- OR = first 15m / 30m / 60m of NY RTH 09:30",
        "- Breakout stop entry; SL = opposite OR side",
        "- Daily SMA200 bias (long only above / short only below)",
        "- Skip if OR width outside 0.10–0.80 × daily ATR(14)",
        "- TP1=1R (50% + BE), TP2=2R; flatten at RTH close",
        "- Cost 1.5 bps RT; daily features warmed from max daily history",
        "",
        "## Data limits",
        "- Yahoo 5m/15m ≈ 60 calendar days",
        "- 1h first-hour OR proxy ≈ 2 years (coarser OR)",
        "",
        "## Results",
        "",
    ]

    print("Downloading NQ=F 15m 60d...")
    m15 = load("NQ=F", "15m", "60d")
    cases.append(run_case("NQ ORB15 +bias 60d", m15, daily, or_minutes=15, **BASE))
    cases.append(
        run_case(
            "NQ ORB15 no-bias 60d",
            m15,
            daily,
            or_minutes=15,
            **{**BASE, "use_daily_bias": False},
        )
    )
    cases.append(run_case("NQ ORB30 +bias 60d", m15, daily, or_minutes=30, **BASE))

    print("Downloading NQ=F 5m 60d...")
    m5 = load("NQ=F", "5m", "60d")
    cases.append(run_case("NQ ORB15 on5m +bias 60d", m5, daily, or_minutes=15, **BASE))

    print("Downloading NQ=F 1h 2y...")
    h1 = load("NQ=F", "1h", "2y")
    cases.append(run_case("NQ ORB60 1h-proxy +bias 2y", h1, daily, or_minutes=60, **BASE))
    cases.append(
        run_case(
            "NQ ORB60 1h-proxy no-bias 2y",
            h1,
            daily,
            or_minutes=60,
            **{**BASE, "use_daily_bias": False},
        )
    )
    cases.append(
        run_case(
            "NQ ORB60 1h-proxy +bias long-only 2y",
            h1,
            daily,
            or_minutes=60,
            **{**BASE, "mode": "long_only"},
        )
    )
    cases.append(
        run_case(
            "NQ ORB60 1h-proxy +bias looseWidth 2y",
            h1,
            daily,
            or_minutes=60,
            **{**BASE, "min_or_atr": 0.05, "max_or_atr": 1.20},
        )
    )

    for item in cases:
        md.append(fmt(*item))

    md += [
        "## Reading guide",
        "- 60d samples are tiny — directional only.",
        "- 2y 1h proxy has more trades but coarser OR definition.",
        "- Weak/negative after costs ⇒ not EA-ready without extra filters (news, OR quality, VWAP).",
        "",
        "Not financial advice.",
        "",
    ]
    text = "\n".join(md)
    (OUT / "ORB_REPORT.md").write_text(text)
    print("=" * 60)
    print(text)


if __name__ == "__main__":
    main()
