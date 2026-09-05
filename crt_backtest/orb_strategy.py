"""
Opening Range Breakout (ORB) for US100 / NQ.

Rules:
1. NY RTH 09:30–16:00 America/New_York
2. OR = first `or_minutes` of RTH (default 15)
3. After OR locks: buy stop @ OR high / sell stop @ OR low
4. Optional daily bias: prior Close > SMA200 → long only; < → short only
5. Width filter: skip if OR/ATR outside [min_or_atr, max_or_atr]
6. SL = opposite OR side
7. TP1 / TP2 in R; optional 50% at TP1 then BE; flatten at RTH close
8. One trade per day
9. Costs: bps round-trip deducted from R
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class Trade:
    direction: str
    day: str
    entry_time: pd.Timestamp
    entry: float
    sl: float
    tp1: float
    tp2: float
    orig_risk: float
    or_high: float
    or_low: float
    exit_time: Optional[pd.Timestamp] = None
    exit: Optional[float] = None
    reason: str = ""
    r_multiple: float = 0.0
    half_closed: bool = False


def _flat(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def to_ny(df: pd.DataFrame) -> pd.DataFrame:
    d = _flat(df).copy()
    if d.index.tz is None:
        d.index = d.index.tz_localize("UTC")
    d.index = d.index.tz_convert("America/New_York")
    return d.sort_index()[["Open", "High", "Low", "Close"]].dropna()


def daily_features(intraday: pd.DataFrame, sma_n: int = 200) -> pd.DataFrame:
    daily = (
        intraday.resample("1D")
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})
        .dropna()
    )
    prev = daily["Close"].shift(1)
    tr = pd.concat(
        [
            daily["High"] - daily["Low"],
            (daily["High"] - prev).abs(),
            (daily["Low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    daily["atr"] = tr.rolling(14).mean()
    daily["sma"] = daily["Close"].rolling(sma_n).mean()
    daily["bias"] = np.where(
        daily["Close"] > daily["sma"],
        1,
        np.where(daily["Close"] < daily["sma"], -1, 0),
    )
    return daily


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
    eq = np.cumsum(rs)
    dd = eq - np.maximum.accumulate(eq)
    wins = rs[rs > 0]
    losses = rs[rs <= 0]
    gw = float(wins.sum()) if len(wins) else 0.0
    gl = float(abs(losses.sum())) if len(losses) else 0.0
    pf = (gw / gl) if gl > 0 else (999.0 if gw > 0 else 0.0)
    return {
        "trades": len(trades),
        "wins": int((rs > 0).sum()),
        "losses": int((rs <= 0).sum()),
        "win_rate": float((rs > 0).mean() * 100.0),
        "avg_r": float(rs.mean()),
        "total_r": float(rs.sum()),
        "max_dd_r": float(dd.min()) if len(dd) else 0.0,
        "profit_factor": float(pf),
        "longs": sum(1 for t in trades if t.direction == "long"),
        "shorts": sum(1 for t in trades if t.direction == "short"),
        "best_r": float(rs.max()),
        "worst_r": float(rs.min()),
    }


def yearly_r(trades: list[Trade]) -> dict:
    rows = []
    for t in trades:
        if t.exit_time is None:
            continue
        rows.append({"year": int(pd.Timestamp(t.exit_time).tz_convert("America/New_York").year), "r": t.r_multiple})
    if not rows:
        return {}
    s = pd.DataFrame(rows).groupby("year")["r"].sum()
    return {int(k): float(v) for k, v in s.items()}


def trades_frame(trades: list[Trade]) -> pd.DataFrame:
    return pd.DataFrame([asdict(t) for t in trades])


def _close_r(tr: Trade, exit_px: float, cost_bps_rt: float) -> float:
    raw = (
        (exit_px - tr.entry) / tr.orig_risk
        if tr.direction == "long"
        else (tr.entry - exit_px) / tr.orig_risk
    )
    cost = (cost_bps_rt / 10000.0) * tr.entry / tr.orig_risk
    if tr.half_closed:
        r_tp1 = abs(tr.entry - tr.tp1) / tr.orig_risk
        return 0.5 * r_tp1 + 0.5 * raw - cost
    return raw - cost


def run_orb(
    intraday: pd.DataFrame,
    or_minutes: int = 15,
    use_daily_bias: bool = True,
    sma_n: int = 200,
    min_or_atr: float = 0.10,
    max_or_atr: float = 0.80,
    tp1_r: float = 1.0,
    tp2_r: float = 2.0,
    partial_at_tp1: bool = True,
    flatten_at_close: bool = True,
    cost_bps_rt: float = 1.0,
    mode: str = "both",  # both | long_only | short_only
    daily_df: pd.DataFrame | None = None,
) -> tuple[list[Trade], dict]:
    df = to_ny(intraday)
    if daily_df is not None:
        daily = daily_features(to_ny(daily_df), sma_n=sma_n)
    else:
        daily = daily_features(df, sma_n=sma_n)

    minutes = df.index.hour * 60 + df.index.minute
    rth = df[(minutes >= 9 * 60 + 30) & (minutes < 16 * 60)].copy()
    trades: list[Trade] = []

    for day, day_bars in rth.groupby(rth.index.date):
        day_bars = day_bars.sort_index()
        or_end = 9 * 60 + 30 + or_minutes
        mins = day_bars.index.hour * 60 + day_bars.index.minute
        or_bars = day_bars[mins < or_end]
        after = day_bars[mins >= or_end]
        if or_bars.empty or after.empty:
            continue

        or_high = float(or_bars["High"].max())
        or_low = float(or_bars["Low"].min())
        or_range = or_high - or_low
        if or_range <= 0:
            continue

        # prior completed daily bar
        day_ts = pd.Timestamp(day).tz_localize("America/New_York")
        prior = daily.loc[daily.index < day_ts].tail(1)
        if prior.empty:
            continue
        prior_atr = float(prior["atr"].iloc[0])
        prior_bias = int(prior["bias"].iloc[0])
        if np.isnan(prior_atr) or prior_atr <= 0:
            continue
        if np.isnan(prior["sma"].iloc[0]):
            continue

        width = or_range / prior_atr
        if width < min_or_atr or width > max_or_atr:
            continue

        allow_long = mode in ("both", "long_only")
        allow_short = mode in ("both", "short_only")
        if use_daily_bias:
            if prior_bias > 0:
                allow_short = False
            elif prior_bias < 0:
                allow_long = False
            else:
                continue

        open_tr: Optional[Trade] = None
        pend_long = allow_long
        pend_short = allow_short

        for ts, bar in after.iterrows():
            if open_tr is not None:
                if open_tr.direction == "long":
                    hit_sl = bar["Low"] <= open_tr.sl
                    hit_tp1 = bar["High"] >= open_tr.tp1
                    hit_tp2 = bar["High"] >= open_tr.tp2
                    gap_sl = bar["Open"] < open_tr.sl
                else:
                    hit_sl = bar["High"] >= open_tr.sl
                    hit_tp1 = bar["Low"] <= open_tr.tp1
                    hit_tp2 = bar["Low"] <= open_tr.tp2
                    gap_sl = bar["Open"] > open_tr.sl

                is_last = ts == after.index[-1]
                if hit_sl and (hit_tp1 or hit_tp2):
                    px = float(bar["Open"]) if gap_sl else open_tr.sl
                    open_tr.exit_time = ts
                    open_tr.exit = px
                    open_tr.reason = "Partial TP1 + SL" if open_tr.half_closed else "SL (conflict)"
                    if open_tr.half_closed:
                        open_tr.r_multiple = _close_r(open_tr, px, cost_bps_rt)
                    else:
                        cost = (cost_bps_rt / 10000.0) * open_tr.entry / open_tr.orig_risk
                        open_tr.r_multiple = -1.0 - cost
                    trades.append(open_tr)
                    open_tr = None
                    break

                if hit_sl:
                    px = float(bar["Open"]) if gap_sl else open_tr.sl
                    open_tr.exit_time = ts
                    open_tr.exit = px
                    open_tr.reason = "Partial TP1 + SL" if open_tr.half_closed else "SL"
                    if open_tr.half_closed:
                        open_tr.r_multiple = _close_r(open_tr, px, cost_bps_rt)
                    else:
                        cost = (cost_bps_rt / 10000.0) * open_tr.entry / open_tr.orig_risk
                        open_tr.r_multiple = -1.0 - cost
                    trades.append(open_tr)
                    open_tr = None
                    break

                if partial_at_tp1 and (not open_tr.half_closed) and hit_tp1:
                    open_tr.half_closed = True
                    open_tr.sl = open_tr.entry  # BE
                    if hit_tp2:
                        open_tr.exit_time = ts
                        open_tr.exit = open_tr.tp2
                        open_tr.reason = "TP1+TP2"
                        open_tr.r_multiple = _close_r(open_tr, open_tr.tp2, cost_bps_rt)
                        trades.append(open_tr)
                        open_tr = None
                        break
                    continue

                if hit_tp2:
                    open_tr.exit_time = ts
                    open_tr.exit = open_tr.tp2
                    open_tr.reason = "TP1+TP2" if open_tr.half_closed else "TP2"
                    open_tr.r_multiple = _close_r(open_tr, open_tr.tp2, cost_bps_rt)
                    trades.append(open_tr)
                    open_tr = None
                    break

                if flatten_at_close and is_last:
                    px = float(bar["Close"])
                    open_tr.exit_time = ts
                    open_tr.exit = px
                    open_tr.reason = "Partial TP1 + EOD" if open_tr.half_closed else "EOD flatten"
                    open_tr.r_multiple = _close_r(open_tr, px, cost_bps_rt)
                    trades.append(open_tr)
                    open_tr = None
                    break
                continue

            # Entries
            if pend_long and bar["High"] >= or_high:
                entry = or_high if bar["Open"] <= or_high else float(bar["Open"])
                risk = entry - or_low
                if risk > 0:
                    open_tr = Trade(
                        direction="long",
                        day=str(day),
                        entry_time=ts,
                        entry=entry,
                        sl=or_low,
                        tp1=entry + tp1_r * risk,
                        tp2=entry + tp2_r * risk,
                        orig_risk=risk,
                        or_high=or_high,
                        or_low=or_low,
                    )
                    pend_long = pend_short = False
                    continue

            if pend_short and bar["Low"] <= or_low:
                entry = or_low if bar["Open"] >= or_low else float(bar["Open"])
                risk = or_high - entry
                if risk > 0:
                    open_tr = Trade(
                        direction="short",
                        day=str(day),
                        entry_time=ts,
                        entry=entry,
                        sl=or_high,
                        tp1=entry - tp1_r * risk,
                        tp2=entry - tp2_r * risk,
                        orig_risk=risk,
                        or_high=or_high,
                        or_low=or_low,
                    )
                    pend_long = pend_short = False
                    continue

        if open_tr is not None:
            last_t = after.index[-1]
            px = float(after.iloc[-1]["Close"])
            open_tr.exit_time = last_t
            open_tr.exit = px
            open_tr.reason = "Partial TP1 + EOD" if open_tr.half_closed else "EOD flatten"
            open_tr.r_multiple = _close_r(open_tr, px, cost_bps_rt)
            trades.append(open_tr)

    return trades, summarize(trades)
