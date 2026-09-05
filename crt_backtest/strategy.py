"""
CRT (Candle Range Theory) backtest.

Rules (strict):
- Range TF: H4 previous closed candle (High/Low/Mid)
- Entry TF: M15 (or H1 proxy for longer history)
- Sweep of CRT High -> bearish confirm close back inside + Close < Open -> SHORT
- Sweep of CRT Low  -> bullish confirm close back inside + Close > Open -> LONG
- SL beyond sweep extreme + ATR buffer
- TP1 = CRT Mid (50%), TP2 = opposite side of CRT range
- Skip if RR to TP2 < 1.5 or SL too large vs ATR
- Max 1 trade per CRT range
- Session filter: London + NY (07:00-21:00 UTC)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class Trade:
    direction: str
    entry_time: pd.Timestamp
    entry: float
    sl: float
    tp1: float
    tp2: float
    orig_risk: float
    exit_time: Optional[pd.Timestamp] = None
    exit: Optional[float] = None
    reason: str = ""
    r_multiple: float = 0.0
    crt_high: float = 0.0
    crt_low: float = 0.0
    half_closed: bool = False


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def to_utc_index(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    return df.sort_index()


def resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    return (
        df.resample(rule, label="left", closed="left")
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})
        .dropna()
    )


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["Close"].shift(1)
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def in_session(ts: pd.Timestamp) -> bool:
    return 7 <= ts.hour < 21


def _r_from_exit(trade: Trade, exit_px: float) -> float:
    risk = trade.orig_risk if trade.orig_risk > 0 else 1e-9
    if trade.direction == "long":
        raw = (exit_px - trade.entry) / risk
    else:
        raw = (trade.entry - exit_px) / risk
    if trade.half_closed:
        r_tp1 = abs(trade.entry - trade.tp1) / risk
        return 0.5 * r_tp1 + 0.5 * raw
    return raw


def run_crt_backtest(
    entry_df: pd.DataFrame,
    range_rule: str = "4h",
    atr_sl_buffer: float = 0.1,
    min_rr: float = 1.5,
    max_sl_atr: float = 3.0,
    use_session_filter: bool = True,
    require_color_confirm: bool = True,
    partial_at_mid: bool = True,
) -> tuple[list[Trade], dict]:
    entry_df = _flatten_columns(entry_df)
    entry_df = to_utc_index(entry_df)
    entry_df = entry_df[["Open", "High", "Low", "Close"]].dropna()

    range_df = resample_ohlc(entry_df, range_rule)
    range_atr = atr(range_df, 14)
    range_times = list(range_df.index)

    trades: list[Trade] = []
    open_trade: Optional[Trade] = None
    swept_high = False
    swept_low = False
    sweep_high_px = np.nan
    sweep_low_px = np.nan
    active_crt_time: Optional[pd.Timestamp] = None
    traded_this_range = False

    for t, bar in entry_df.iterrows():
        forming = -1
        for j in range(len(range_times) - 1, -1, -1):
            if range_times[j] <= t:
                forming = j
                break
        if forming < 1:
            continue

        crt_time = range_times[forming - 1]
        crt = range_df.loc[crt_time]
        crt_high = float(crt["High"])
        crt_low = float(crt["Low"])
        crt_mid = (crt_high + crt_low) / 2.0
        crt_atr_val = range_atr.loc[crt_time] if crt_time in range_atr.index else np.nan
        crt_atr = float(crt_atr_val) if pd.notna(crt_atr_val) else np.nan

        if active_crt_time != crt_time:
            active_crt_time = crt_time
            swept_high = False
            swept_low = False
            sweep_high_px = np.nan
            sweep_low_px = np.nan
            traded_this_range = False

        # --- manage open trade ---
        if open_trade is not None:
            if open_trade.direction == "long":
                hit_sl = bar["Low"] <= open_trade.sl
                hit_tp1 = bar["High"] >= open_trade.tp1
                hit_tp2 = bar["High"] >= open_trade.tp2
            else:
                hit_sl = bar["High"] >= open_trade.sl
                hit_tp1 = bar["Low"] <= open_trade.tp1
                hit_tp2 = bar["Low"] <= open_trade.tp2

            # Same-bar SL vs TP: conservative -> SL wins
            if hit_sl and (hit_tp1 or hit_tp2):
                if open_trade.half_closed:
                    # SL was at BE after partial; remaining half flat, keep +0.5R from TP1
                    open_trade.exit = open_trade.entry
                    open_trade.reason = "Partial TP1 + BE"
                    open_trade.r_multiple = 0.5 * (abs(open_trade.entry - open_trade.tp1) / open_trade.orig_risk)
                else:
                    open_trade.exit = open_trade.sl
                    open_trade.reason = "SL (same-bar conflict)"
                    open_trade.r_multiple = -1.0
                open_trade.exit_time = t
                trades.append(open_trade)
                open_trade = None
                continue

            if hit_sl:
                if open_trade.half_closed:
                    open_trade.exit = open_trade.entry
                    open_trade.reason = "Partial TP1 + BE"
                    open_trade.r_multiple = 0.5 * (abs(open_trade.entry - open_trade.tp1) / open_trade.orig_risk)
                else:
                    open_trade.exit = open_trade.sl
                    open_trade.reason = "SL"
                    open_trade.r_multiple = -1.0
                open_trade.exit_time = t
                trades.append(open_trade)
                open_trade = None
                continue

            if partial_at_mid and (not open_trade.half_closed) and hit_tp1:
                open_trade.half_closed = True
                open_trade.sl = open_trade.entry  # BE
                if hit_tp2:
                    open_trade.exit_time = t
                    open_trade.exit = open_trade.tp2
                    open_trade.reason = "TP1+TP2"
                    open_trade.r_multiple = _r_from_exit(open_trade, open_trade.tp2)
                    trades.append(open_trade)
                    open_trade = None
                continue

            if hit_tp2:
                open_trade.exit_time = t
                open_trade.exit = open_trade.tp2
                open_trade.reason = "TP1+TP2" if open_trade.half_closed else "TP2"
                open_trade.r_multiple = _r_from_exit(open_trade, open_trade.tp2)
                trades.append(open_trade)
                open_trade = None
                continue

            continue  # in trade: no new entries

        # --- sweeps ---
        if bar["High"] > crt_high:
            swept_high = True
            sweep_high_px = bar["High"] if np.isnan(sweep_high_px) else max(sweep_high_px, float(bar["High"]))
        if bar["Low"] < crt_low:
            swept_low = True
            sweep_low_px = bar["Low"] if np.isnan(sweep_low_px) else min(sweep_low_px, float(bar["Low"]))

        if traded_this_range or np.isnan(crt_atr) or crt_atr <= 0:
            continue
        if use_session_filter and not in_session(t):
            continue

        close = float(bar["Close"])
        open_ = float(bar["Open"])
        bullish = close > open_
        bearish = close < open_

        # SHORT: sweep high, close back inside range (below high), bearish confirm.
        # Prefer entry still above mid so mid is a valid first target.
        if swept_high and close < crt_high:
            if (not require_color_confirm) or bearish:
                entry = close
                sl = float(sweep_high_px) + atr_sl_buffer * crt_atr
                tp2 = crt_low
                # If already at/through mid, skip mid partial — target opposite side only.
                tp1 = crt_mid if entry > crt_mid else tp2
                risk = abs(entry - sl)
                reward = abs(entry - tp2)
                if risk > 0 and reward / risk >= min_rr and risk <= max_sl_atr * crt_atr:
                    open_trade = Trade(
                        direction="short",
                        entry_time=t,
                        entry=entry,
                        sl=sl,
                        tp1=tp1,
                        tp2=tp2,
                        orig_risk=risk,
                        crt_high=crt_high,
                        crt_low=crt_low,
                    )
                    traded_this_range = True
                    continue

        # LONG: sweep low, close back inside (above low), bullish confirm.
        if swept_low and close > crt_low:
            if (not require_color_confirm) or bullish:
                entry = close
                sl = float(sweep_low_px) - atr_sl_buffer * crt_atr
                tp2 = crt_high
                tp1 = crt_mid if entry < crt_mid else tp2
                risk = abs(entry - sl)
                reward = abs(entry - tp2)
                if risk > 0 and reward / risk >= min_rr and risk <= max_sl_atr * crt_atr:
                    open_trade = Trade(
                        direction="long",
                        entry_time=t,
                        entry=entry,
                        sl=sl,
                        tp1=tp1,
                        tp2=tp2,
                        orig_risk=risk,
                        crt_high=crt_high,
                        crt_low=crt_low,
                    )
                    traded_this_range = True

    if open_trade is not None:
        last_t = entry_df.index[-1]
        last_px = float(entry_df.iloc[-1]["Close"])
        open_trade.exit_time = last_t
        open_trade.exit = last_px
        open_trade.reason = "Partial TP1 + EOD" if open_trade.half_closed else "EOD"
        open_trade.r_multiple = _r_from_exit(open_trade, last_px)
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
        }

    rs = np.array([t.r_multiple for t in trades], dtype=float)
    equity = np.cumsum(rs)
    peak = np.maximum.accumulate(equity)
    dd = equity - peak
    wins = rs[rs > 0]
    losses = rs[rs <= 0]
    gross_win = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(abs(losses.sum())) if len(losses) else 0.0
    pf = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)

    return {
        "trades": len(trades),
        "wins": int((rs > 0).sum()),
        "losses": int((rs <= 0).sum()),
        "win_rate": float((rs > 0).mean() * 100.0),
        "avg_r": float(rs.mean()),
        "total_r": float(rs.sum()),
        "max_dd_r": float(dd.min()) if len(dd) else 0.0,
        "profit_factor": float(pf) if np.isfinite(pf) else 999.0,
        "longs": sum(1 for t in trades if t.direction == "long"),
        "shorts": sum(1 for t in trades if t.direction == "short"),
        "best_r": float(rs.max()),
        "worst_r": float(rs.min()),
    }


def trades_to_frame(trades: list[Trade]) -> pd.DataFrame:
    return pd.DataFrame([asdict(t) for t in trades])
