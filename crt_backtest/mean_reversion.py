"""
Mean-reversion EA candidates (designed to NOT just ride a bull).

A) Connors-style RSI(2) dip-buy (equities/indices, long-only):
   - Long when RSI(2) <= rsi_buy AND Close > SMA(trend)
   - Exit when RSI(2) >= rsi_exit OR Close < SMA(exit_sma) [optional]
   - Stop: entry - stop_atr * ATR(atr_n)
   - Fill next open after signal close

B) Bollinger fade (FX-friendly, long/short):
   - Long when Close < BB_lower(bb_n, bb_k) and optional ADX < adx_max (range filter)
   - Short when Close > BB_upper
   - Exit at BB_mid (or opposite band)
   - Stop: entry +/- stop_atr * ATR
   - Fill next open

Always report buy&hold in same 2×ATR unit for the test window.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
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
    tp: float
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


def to_utc(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    return df.sort_index()


def atr_series(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = df["Close"].shift(1)
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev).abs(),
            (df["Low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(n).mean()


def rsi(series: pd.Series, n: int = 2) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0.0)
    down = -delta.clip(upper=0.0)
    # Wilder-style for n=2 Connors often uses simple SMA; use EMA(alpha=1/n) Wilder
    avg_up = up.ewm(alpha=1 / n, adjust=False).mean()
    avg_down = down.ewm(alpha=1 / n, adjust=False).mean()
    rs = avg_up / avg_down.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = pd.concat(
        [
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = pd.Series(tr, index=df.index).ewm(alpha=1 / n, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / atr
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)).fillna(0)
    return dx.ewm(alpha=1 / n, adjust=False).mean()


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
    rows = [{"year": t.exit_time.tz_convert("UTC").year, "r": t.r_multiple} for t in trades if t.exit_time is not None]
    return pd.DataFrame(rows).groupby("year")["r"].sum().sort_index()


def trades_frame(trades: list[Trade]) -> pd.DataFrame:
    return pd.DataFrame([asdict(t) for t in trades])


def buy_hold_r(df: pd.DataFrame, window_start: pd.Timestamp, atr_n: int = 14, atr_stop: float = 2.0) -> dict:
    d = df.copy()
    d["atr"] = atr_series(d, atr_n)
    w = d[d.index >= window_start].dropna(subset=["atr", "Close"])
    if w.empty:
        return {"bh_pct": 0.0, "bh_r": 0.0}
    entry = float(w.iloc[0]["Close"])
    exit_ = float(w.iloc[-1]["Close"])
    risk = atr_stop * float(w.iloc[0]["atr"])
    return {
        "bh_pct": (exit_ / entry - 1.0) * 100.0,
        "bh_r": (exit_ - entry) / risk if risk > 0 else 0.0,
    }


def _close_trade(tr: Trade, t, px: float, reason: str, cost_bps_rt: float, i: int, entry_i: int):
    tr.exit_time = t
    tr.exit = float(px)
    tr.reason = reason
    tr.bars_held = i - entry_i
    raw = (tr.exit - tr.entry) / tr.orig_risk if tr.direction == "long" else (tr.entry - tr.exit) / tr.orig_risk
    cost_r = (cost_bps_rt / 10000.0) * tr.entry / tr.orig_risk
    tr.r_multiple = raw - cost_r
    return tr


def run_rsi2(
    df: pd.DataFrame,
    rsi_n: int = 2,
    rsi_buy: float = 10.0,
    rsi_exit: float = 70.0,
    trend_sma: int = 200,
    atr_n: int = 14,
    atr_stop: float = 2.0,
    cost_bps_rt: float = 2.0,
    mode: str = "long_only",  # long_only | long_short
) -> tuple[list[Trade], dict]:
    d = _flat(df).copy()
    d = to_utc(d)[["Open", "High", "Low", "Close"]].dropna()
    d["rsi"] = rsi(d["Close"], rsi_n)
    d["sma"] = d["Close"].rolling(trend_sma).mean()
    d["atr"] = atr_series(d, atr_n)

    trades: list[Trade] = []
    open_tr: Optional[Trade] = None
    pending: Optional[dict] = None
    entry_i = -1
    idx = list(d.index)

    for i, t in enumerate(idx):
        row = d.iloc[i]

        if pending is not None and open_tr is None:
            entry = float(row["Open"])
            atr = pending["atr"]
            direction = pending["direction"]
            if atr > 0 and not np.isnan(atr):
                if direction == "long":
                    sl = entry - atr_stop * atr
                    tp = entry + 10 * atr_stop * atr  # unused soft; RSI exit primary
                else:
                    sl = entry + atr_stop * atr
                    tp = entry - 10 * atr_stop * atr
                risk = abs(entry - sl)
                if risk > 0:
                    open_tr = Trade(
                        direction=direction,
                        signal_time=pending["signal_time"],
                        entry_time=t,
                        entry=entry,
                        sl=sl,
                        tp=tp,
                        orig_risk=risk,
                    )
                    entry_i = i
            pending = None

        if open_tr is not None and open_tr.entry_time != t:
            hit_sl = row["Low"] <= open_tr.sl if open_tr.direction == "long" else row["High"] >= open_tr.sl
            rsi_exit_hit = (
                (row["rsi"] >= rsi_exit) if open_tr.direction == "long" else (row["rsi"] <= (100 - rsi_exit))
            )
            if hit_sl:
                px = float(row["Open"]) if (
                    (open_tr.direction == "long" and row["Open"] < open_tr.sl)
                    or (open_tr.direction == "short" and row["Open"] > open_tr.sl)
                ) else open_tr.sl
                trades.append(_close_trade(open_tr, t, px, "SL", cost_bps_rt, i, entry_i))
                open_tr = None
            elif rsi_exit_hit and not np.isnan(row["rsi"]):
                trades.append(_close_trade(open_tr, t, float(row["Close"]), "RSI exit", cost_bps_rt, i, entry_i))
                open_tr = None
            continue

        if open_tr is not None or pending is not None:
            continue
        if np.isnan(row["rsi"]) or np.isnan(row["sma"]) or np.isnan(row["atr"]):
            continue

        if mode in ("long_only", "long_short") and row["rsi"] <= rsi_buy and row["Close"] > row["sma"]:
            pending = {"direction": "long", "signal_time": t, "atr": float(row["atr"])}
        elif mode == "long_short" and row["rsi"] >= (100 - rsi_buy) and row["Close"] < row["sma"]:
            pending = {"direction": "short", "signal_time": t, "atr": float(row["atr"])}

    if open_tr is not None:
        trades.append(_close_trade(open_tr, idx[-1], float(d.iloc[-1]["Close"]), "EOD", cost_bps_rt, len(idx) - 1, entry_i))

    return trades, summarize(trades)


def run_bollinger_mr(
    df: pd.DataFrame,
    bb_n: int = 20,
    bb_k: float = 2.0,
    atr_n: int = 14,
    atr_stop: float = 2.0,
    adx_n: int = 14,
    adx_max: float = 25.0,
    use_adx_filter: bool = True,
    cost_bps_rt: float = 2.0,
    mode: str = "long_short",
) -> tuple[list[Trade], dict]:
    d = _flat(df).copy()
    d = to_utc(d)[["Open", "High", "Low", "Close"]].dropna()
    mid = d["Close"].rolling(bb_n).mean()
    std = d["Close"].rolling(bb_n).std(ddof=0)
    d["bb_mid"] = mid
    d["bb_upper"] = mid + bb_k * std
    d["bb_lower"] = mid - bb_k * std
    d["atr"] = atr_series(d, atr_n)
    d["adx"] = adx(d, adx_n)

    trades: list[Trade] = []
    open_tr: Optional[Trade] = None
    pending: Optional[dict] = None
    entry_i = -1
    idx = list(d.index)

    for i, t in enumerate(idx):
        row = d.iloc[i]

        if pending is not None and open_tr is None:
            entry = float(row["Open"])
            atr = pending["atr"]
            direction = pending["direction"]
            mid_px = pending["mid"]
            if atr > 0 and not np.isnan(atr):
                if direction == "long":
                    sl = entry - atr_stop * atr
                    tp = mid_px
                else:
                    sl = entry + atr_stop * atr
                    tp = mid_px
                risk = abs(entry - sl)
                # skip if TP is on wrong side or RR to mid too small
                reward = abs(tp - entry)
                if risk > 0 and reward / risk >= 0.4:
                    open_tr = Trade(
                        direction=direction,
                        signal_time=pending["signal_time"],
                        entry_time=t,
                        entry=entry,
                        sl=sl,
                        tp=float(tp),
                        orig_risk=risk,
                    )
                    entry_i = i
            pending = None

        if open_tr is not None and open_tr.entry_time != t:
            if open_tr.direction == "long":
                hit_sl = row["Low"] <= open_tr.sl
                hit_tp = row["High"] >= open_tr.tp
            else:
                hit_sl = row["High"] >= open_tr.sl
                hit_tp = row["Low"] <= open_tr.tp

            if hit_sl and hit_tp:
                # conservative: SL
                px = float(row["Open"]) if (
                    (open_tr.direction == "long" and row["Open"] < open_tr.sl)
                    or (open_tr.direction == "short" and row["Open"] > open_tr.sl)
                ) else open_tr.sl
                trades.append(_close_trade(open_tr, t, px, "SL (conflict)", cost_bps_rt, i, entry_i))
                open_tr = None
            elif hit_sl:
                px = float(row["Open"]) if (
                    (open_tr.direction == "long" and row["Open"] < open_tr.sl)
                    or (open_tr.direction == "short" and row["Open"] > open_tr.sl)
                ) else open_tr.sl
                trades.append(_close_trade(open_tr, t, px, "SL", cost_bps_rt, i, entry_i))
                open_tr = None
            elif hit_tp:
                trades.append(_close_trade(open_tr, t, open_tr.tp, "BB mid TP", cost_bps_rt, i, entry_i))
                open_tr = None
            continue

        if open_tr is not None or pending is not None:
            continue
        if np.isnan(row["bb_lower"]) or np.isnan(row["atr"]) or np.isnan(row["adx"]):
            continue
        if use_adx_filter and row["adx"] > adx_max:
            continue

        if mode in ("long_short", "long_only") and row["Close"] < row["bb_lower"]:
            pending = {
                "direction": "long",
                "signal_time": t,
                "atr": float(row["atr"]),
                "mid": float(row["bb_mid"]),
            }
        elif mode in ("long_short", "short_only") and row["Close"] > row["bb_upper"]:
            pending = {
                "direction": "short",
                "signal_time": t,
                "atr": float(row["atr"]),
                "mid": float(row["bb_mid"]),
            }

    if open_tr is not None:
        trades.append(_close_trade(open_tr, idx[-1], float(d.iloc[-1]["Close"]), "EOD", cost_bps_rt, len(idx) - 1, entry_i))

    return trades, summarize(trades)
