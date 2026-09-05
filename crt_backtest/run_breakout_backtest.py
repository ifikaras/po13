#!/usr/bin/env python3
"""Run Donchian/ATR breakout backtests on max available daily history."""

from __future__ import annotations

import json
from pathlib import Path

import yfinance as yf

from breakout_strategy import run_breakout, trades_frame, yearly_r, _flat
from strategy import to_utc_index

OUT = Path(__file__).resolve().parent / "results"
OUT.mkdir(parents=True, exist_ok=True)


def download_max(symbol: str):
    df = yf.download(symbol, period="max", interval="1d", progress=False, auto_adjust=True)
    df = _flat(df)
    if df.empty:
        raise RuntimeError(f"No data for {symbol}")
    df = df[["Open", "High", "Low", "Close"]].dropna()
    return to_utc_index(df)


def fmt(name, stats, start, end, years: dict | None = None) -> str:
    lines = [
        f"### {name}",
        f"- Period: {start.date()} → {end.date()} ({(end - start).days / 365.25:.1f}y)",
        f"- Trades: {stats['trades']} (L {stats['longs']} / S {stats['shorts']})",
        f"- Win rate: {stats['win_rate']:.1f}% ({stats['wins']}W / {stats['losses']}L)",
        f"- Total R: {stats['total_r']:+.2f}R",
        f"- Avg R / trade: {stats['avg_r']:+.3f}R",
        f"- Profit factor: {stats['profit_factor']:.2f}",
        f"- Max DD: {stats['max_dd_r']:.2f}R",
        f"- Best / Worst: {stats['best_r']:+.2f}R / {stats['worst_r']:+.2f}R",
        f"- Avg bars held: {stats['avg_bars']:.1f}",
    ]
    if years:
        # compact yearly
        parts = [f"{y}:{v:+.1f}" for y, v in years.items()]
        # show last 10 + first hint
        lines.append(f"- Yearly R (all): {', '.join(parts)}")
        pos = sum(1 for v in years.values() if v > 0)
        lines.append(f"- Positive years: {pos}/{len(years)} ({100 * pos / max(len(years), 1):.0f}%)")
    lines.append("")
    return "\n".join(lines)


def run_case(label, symbol, df, **kwargs):
    trades, stats = run_breakout(df, **kwargs)
    start, end = df.index.min(), df.index.max()
    y = yearly_r(trades)
    years = {int(k): float(v) for k, v in y.items()} if len(y) else {}
    print(fmt(label, stats, start, end, years))
    safe = (
        label.replace(" ", "_")
        .replace("/", "_")
        .replace("+", "plus")
        .replace("=", "")
        .replace("(", "")
        .replace(")", "")
    )
    trades_frame(trades).to_csv(OUT / f"{safe}_trades.csv", index=False)
    payload = {
        "label": label,
        "symbol": symbol,
        "start": str(start),
        "end": str(end),
        "params": kwargs,
        "yearly_r": years,
        **stats,
    }
    (OUT / f"{safe}_stats.json").write_text(json.dumps(payload, indent=2, default=str))
    return label, stats, start, end, years


def main():
    # Primary ruleset
    primary = dict(
        entry_n=20,
        exit_n=10,
        atr_n=20,
        atr_stop=2.0,
        atr_trail=3.0,
        sma_n=200,
        use_sma_filter=True,
        use_donch_exit=True,
        use_atr_trail=True,
        cost_bps_rt=2.0,
    )

    symbols = [
        ("NQ=F", "US100/NQ", 3.0),       # futures: slightly higher cost proxy
        ("EURUSD=X", "EURUSD", 1.5),
        ("GC=F", "Gold", 3.0),
        ("^GSPC", "S&P500", 1.0),
    ]

    cases = []
    md = [
        "# Donchian / ATR Trend Breakout Backtest",
        "",
        "## Rules (chosen EA candidate)",
        "1. **TF:** Daily",
        "2. **Signal** on close; **fill next open** (no lookahead)",
        "3. **Entry:** Close breaks prior 20-day Donchian high/low",
        "4. **Filter:** SMA200 — longs only above, shorts only below",
        "5. **Initial stop:** 2×ATR(20)",
        "6. **Trail:** Chandelier 3×ATR from prior close (never loosens)",
        "7. **Exit also on:** opposite 10-day Donchian close break",
        "8. One position, no pyramid",
        "9. Round-trip cost deducted (symbol-dependent bps)",
        "",
        "## Results",
        "",
    ]

    for symbol, name, cost in symbols:
        print(f"Downloading {symbol} max history...")
        df = download_max(symbol)
        params = {**primary, "cost_bps_rt": cost, "mode": "long_short"}
        cases.append(run_case(f"{name} D1 breakout L/S", symbol, df, **params))

        # Indices: also long-only (more natural for equity indexes)
        if symbol in ("NQ=F", "^GSPC"):
            params_lo = {**primary, "cost_bps_rt": cost, "mode": "long_only"}
            cases.append(run_case(f"{name} D1 breakout LONG-ONLY", symbol, df, **params_lo))

    # Ablations on NQ long-only
    print("Downloading NQ=F for ablations...")
    nq = download_max("NQ=F")
    cases.append(
        run_case(
            "US100/NQ LONG-ONLY no SMA filter",
            "NQ=F",
            nq,
            **{**primary, "cost_bps_rt": 3.0, "mode": "long_only", "use_sma_filter": False},
        )
    )
    cases.append(
        run_case(
            "US100/NQ LONG-ONLY entry55/exit20",
            "NQ=F",
            nq,
            entry_n=55,
            exit_n=20,
            atr_n=20,
            atr_stop=2.0,
            atr_trail=3.0,
            sma_n=200,
            mode="long_only",
            use_sma_filter=True,
            use_donch_exit=True,
            use_atr_trail=True,
            cost_bps_rt=3.0,
        )
    )

    for label, stats, start, end, years in cases:
        md.append(fmt(label, stats, start, end, years))

    md += [
        "## Notes",
        "- Yahoo daily OHLC; not broker MT5 ticks.",
        "- Costs are a simple bps proxy, not full commission schedule.",
        "- Same-bar stop uses conservative fill (gap -> open).",
        "- Not financial advice.",
        "",
    ]
    text = "\n".join(md)
    (OUT / "BREAKOUT_REPORT.md").write_text(text)
    print("=" * 60)
    print(text)


if __name__ == "__main__":
    main()
