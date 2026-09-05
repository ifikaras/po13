"""
Donchian / ATR trend-following breakout (EA candidate).

Chosen rules (mechanical, few knobs, higher TF):

1. Timeframe: Daily
2. Signal on day T close; fill at day T+1 open (no lookahead)
3. Entry long:  Close[T] > highest(High, N)[T-1]
   Entry short: Close[T] < lowest(Low, N)[T-1]
4. Trend filter (SMA200):
   - Long only if Close[T] > SMA200[T]
   - Short only if Close[T] < SMA200[T]
5. Initial stop: entry +/- k * ATR(atr_n)  (ATR from signal bar T)
6. Exit (whichever first):
   - Hard stop hit (intrabar, conservative: stop before target logic)
   - Donchian exit: long exits if Close < lowest(Low, exit_n)[prev]
                    short exits if Close > highest(High, exit_n)[prev]
   - Optional ATR chandelier trail (never loosens)
7. One position at a time; no pyramiding
8. Modes: long_short | long_only | short_only

Costs: fixed bps round-trip deducted from each trade's R (approx).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class Trade:
    direction: str
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    entry: float
    sl: float
    orig_risk: float
    exit_time: Optional[pd.Timestamp] = None
    exit: Optional[float] = None
    reason: str = ""
    r_multiple: float = 0.0
    bars_held: int = 0


def _flat(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def prepare(df: pd.DataFrame, entry_n: int, exit_n: int, atr_n: int, sma_n: int) -> pd.DataFrame:
    df = _flat(df).copy()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    df = df[["Open", "High", "Low", "Close"]].dropna().sort_index()

    prev_high = df["High"].shift(1)
    prev_low = df["Low"].shift(1)
    df["donch_high"] = prev_high.rolling(entry_n).max()
    df["donch_low"] = prev_low.rolling(entry_n).min()
    df["exit_low"] = prev_low.rolling(exit_n).min()
    df["exit_high"] = prev_high.rolling(exit_n).max()

    prev_close = df["Close"].shift(1)
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["atr"] = tr.rolling(atr_n).mean()
    df["sma"] = df["Close"].rolling(sma_n).mean()
    return df


def run_breakout(
    df: pd.DataFrame,
    entry_n: int = 20,
    exit_n: int = 10,
    atr_n: int = 20,
    atr_stop: float = 2.0,
    atr_trail: float = 3.0,
    sma_n: int = 200,
    mode: str = "long_short",  # long_short | long_only | short_only
    use_sma_filter: bool = True,
    use_donch_exit: bool = True,
    use_atr_trail: bool = True,
    cost_bps_rt: float = 2.0,  # round-trip cost in basis points of price
) -> tuple[list[Trade], dict]:
    data = prepare(df, entry_n, exit_n, atr_n, sma_n)
    trades: list[Trade] = []
    open_trade: Optional[Trade] = None
    pending: Optional[dict] = None  # fill next open

    idx = list(data.index)
    for i, t in enumerate(idx):
        row = data.iloc[i]

        # --- fill pending entry at today's open ---
        if pending is not None and open_trade is None:
            entry = float(row["Open"])
            direction = pending["direction"]
            atr = pending["atr"]
            if atr <= 0 or np.isnan(atr):
                pending = None
            else:
                if direction == "long":
                    sl = entry - atr_stop * atr
                else:
                    sl = entry + atr_stop * atr
                risk = abs(entry - sl)
                if risk <= 0:
                    pending = None
                else:
                    open_trade = Trade(
                        direction=direction,
                        signal_time=pending["signal_time"],
                        entry_time=t,
                        entry=entry,
                        sl=sl,
                        orig_risk=risk,
                    )
                    pending = None

        # --- manage open trade on this bar ---
        if open_trade is not None and open_trade.entry_time != t:
            # update chandelier trail from prior close (no lookahead)
            prev = data.iloc[i - 1]
            if use_atr_trail and not np.isnan(prev["atr"]) and prev["atr"] > 0:
                if open_trade.direction == "long":
                    trail = float(prev["Close"]) - atr_trail * float(prev["atr"])
                    open_trade.sl = max(open_trade.sl, trail)
                else:
                    trail = float(prev["Close"]) + atr_trail * float(prev["atr"])
                    open_trade.sl = min(open_trade.sl, trail)

            hit_sl = False
            exit_px = None
            reason = ""

            if open_trade.direction == "long":
                if row["Low"] <= open_trade.sl:
                    hit_sl = True
                    # if gap below stop, fill at open
                    exit_px = float(row["Open"]) if row["Open"] < open_trade.sl else open_trade.sl
                    reason = "SL/Trail"
                elif use_donch_exit and not np.isnan(row["exit_low"]) and row["Close"] < row["exit_low"]:
                    exit_px = float(row["Close"])
                    reason = "Donchian exit"
            else:
                if row["High"] >= open_trade.sl:
                    hit_sl = True
                    exit_px = float(row["Open"]) if row["Open"] > open_trade.sl else open_trade.sl
                    reason = "SL/Trail"
                elif use_donch_exit and not np.isnan(row["exit_high"]) and row["Close"] > row["exit_high"]:
                    exit_px = float(row["Close"])
                    reason = "Donchian exit"

            if exit_px is not None:
                open_trade.exit_time = t
                open_trade.exit = float(exit_px)
                open_trade.reason = reason
                open_trade.bars_held = i - idx.index(open_trade.entry_time)
                raw = (
                    (open_trade.exit - open_trade.entry) / open_trade.orig_risk
                    if open_trade.direction == "long"
                    else (open_trade.entry - open_trade.exit) / open_trade.orig_risk
                )
                # cost in R units
                cost_r = (cost_bps_rt / 10000.0) * open_trade.entry / open_trade.orig_risk
                open_trade.r_multiple = raw - cost_r
                trades.append(open_trade)
                open_trade = None

        # --- new signals on close (only if flat and no pending) ---
        if open_trade is not None or pending is not None:
            continue
        if np.isnan(row["donch_high"]) or np.isnan(row["atr"]) or np.isnan(row["sma"]):
            continue

        long_break = row["Close"] > row["donch_high"]
        short_break = row["Close"] < row["donch_low"]
        long_ok = (not use_sma_filter) or (row["Close"] > row["sma"])
        short_ok = (not use_sma_filter) or (row["Close"] < row["sma"])

        if mode in ("long_short", "long_only") and long_break and long_ok:
            pending = {"direction": "long", "signal_time": t, "atr": float(row["atr"])}
        elif mode in ("long_short", "short_only") and short_break and short_ok:
            pending = {"direction": "short", "signal_time": t, "atr": float(row["atr"])}

    # EOD flatten
    if open_trade is not None:
        last_t = idx[-1]
        last_px = float(data.iloc[-1]["Close"])
        open_trade.exit_time = last_t
        open_trade.exit = last_px
        open_trade.reason = "EOD"
        open_trade.bars_held = len(idx) - 1 - idx.index(open_trade.entry_time)
        raw = (
            (last_px - open_trade.entry) / open_trade.orig_risk
            if open_trade.direction == "long"
            else (open_trade.entry - last_px) / open_trade.orig_risk
        )
        cost_r = (cost_bps_rt / 10000.0) * open_trade.entry / open_trade.orig_risk
        open_trade.r_multiple = raw - cost_r
        trades.append(open_trade)

    return trades, summarize(trades)


def summarize(trades: list[Trade]) -> dict:
    if not trades:
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "avg_r": 0.0,
            "total_r": 0.0,
            "max_dd_r": 0.0,
            "profit_factor": 0.0,
            "longs": 0,
            "shorts": 0,
            "best_r": 0.0,
            "worst_r": 0.0,
            "avg_bars": 0.0,
            "pct_time_in_market": 0.0,
        }
    rs = np.array([t.r_multiple for t in trades], dtype=float)
    equity = np.cumsum(rs)
    peak = np.maximum.accumulate(equity)
    dd = equity - peak
    wins = rs[rs > 0]
    losses = rs[rs <= 0]
    gw = float(wins.sum()) if len(wins) else 0.0
    gl = float(abs(losses.sum())) if len(losses) else 0.0
    pf = (gw / gl) if gl > 0 else (999.0 if gw > 0 else 0.0)
    return {
        "trades": len(trades),
        "wins": int((rs > 0).sum()),
        "losses": int((rs <= 0).sum()),
        "win_rate": float((rs > 0).mean() * 100),
        "avg_r": float(rs.mean()),
        "total_r": float(rs.sum()),
        "max_dd_r": float(dd.min()) if len(dd) else 0.0,
        "profit_factor": float(pf),
        "longs": sum(1 for t in trades if t.direction == "long"),
        "shorts": sum(1 for t in trades if t.direction == "short"),
        "best_r": float(rs.max()),
        "worst_r": float(rs.min()),
        "avg_bars": float(np.mean([t.bars_held for t in trades])),
    }


def yearly_r(trades: list[Trade]) -> pd.Series:
    if not trades:
        return pd.Series(dtype=float)
    rows = []
    for t in trades:
        if t.exit_time is None:
            continue
        rows.append({"year": t.exit_time.tz_convert("UTC").year, "r": t.r_multiple})
    df = pd.DataFrame(rows)
    return df.groupby("year")["r"].sum().sort_index()


def trades_frame(trades: list[Trade]) -> pd.DataFrame:
    return pd.DataFrame([asdict(t) for t in trades])
