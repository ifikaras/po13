"""
Recommended practical bot: Index SMA200 crash filter.

Not an alpha/scalping EA. Goal = capture most of the index drift with
much smaller left-tail drawdowns than buy&hold.

Rules (Daily):
1. Instrument: US100 (NQ) or SPX
2. If yesterday Close > SMA200 → stay/go LONG at today's open (or stay invested)
3. If yesterday Close <= SMA200 → FLAT / cash (exit at today's open)
4. No shorts, no pyramiding, no intraday
5. Optional: only rebalance on daily close cross (fewer flips)

This is a risk overlay on buy&hold, not a CRT/breakout alpha system.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class PositionDay:
    time: pd.Timestamp
    position: float  # 0 or 1
    close: float
    equity: float


def sma200_filter_equity(df: pd.DataFrame, sma_n: int = 200) -> pd.DataFrame:
    d = df.copy()
    d["sma"] = d["Close"].rolling(sma_n).mean()
    # Signal on prior close; position for today
    d["signal"] = (d["Close"] > d["sma"]).astype(float)
    d["position"] = d["signal"].shift(1).fillna(0.0)
    d["ret"] = d["Close"].pct_change().fillna(0.0)
    d["strat_ret"] = d["ret"] * d["position"]
    d["equity"] = (1.0 + d["strat_ret"]).cumprod()
    d["bh_equity"] = (1.0 + d["ret"]).cumprod()
    return d


def summarize_overlay(d: pd.DataFrame) -> dict:
    eq = d["equity"].dropna()
    bh = d["bh_equity"].dropna()
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    def _stats(x):
        total = (x.iloc[-1] / x.iloc[0] - 1) * 100
        cagr = ((x.iloc[-1] / x.iloc[0]) ** (1 / years) - 1) * 100 if years > 0 else 0
        dd = (x / x.cummax() - 1).min() * 100
        return total, cagr, dd
    st_total, st_cagr, st_dd = _stats(eq)
    bh_total, bh_cagr, bh_dd = _stats(bh)
    return {
        "years": years,
        "time_in_market_pct": float(d["position"].mean() * 100),
        "strategy_total_pct": st_total,
        "strategy_cagr": st_cagr,
        "strategy_max_dd": st_dd,
        "bh_total_pct": bh_total,
        "bh_cagr": bh_cagr,
        "bh_max_dd": bh_dd,
    }
