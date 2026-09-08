"""Weather edge paper sim — BUY NO when forecast disagrees with YES price."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from polymarket_paper.http_util import get_json

GAMMA = "https://gamma-api.polymarket.com"

CITY_COORDS: dict[str, tuple[float, float, str]] = {
    "toronto": (43.65, -79.38, "America/Toronto"),
    "london": (51.51, -0.13, "Europe/London"),
    "new york": (40.71, -74.01, "America/New_York"),
    "hong kong": (22.32, 114.17, "Asia/Hong_Kong"),
    "tokyo": (35.68, 139.69, "Asia/Tokyo"),
    "helsinki": (60.17, 24.94, "Europe/Helsinki"),
    "shanghai": (31.23, 121.47, "Asia/Shanghai"),
    "paris": (48.86, 2.35, "Europe/Paris"),
    "chicago": (41.88, -87.63, "America/Chicago"),
    "miami": (25.76, -80.19, "America/New_York"),
}


@dataclass
class PaperPosition:
    market_id: str
    question: str
    side: str
    entry_price: float
    size_usd: float
    shares: float
    model_yes: float
    opened_at: str


@dataclass
class WeatherState:
    bankroll: float
    starting_bankroll: float
    positions: list[PaperPosition] = field(default_factory=list)
    closed_pnl: float = 0.0
    cycles: int = 0
    signals: int = 0
    log: list[str] = field(default_factory=list)


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bucket_prob(mu: float, sigma: float, low: float | None, high: float | None) -> float:
    if low is None and high is not None:
        return norm_cdf((high + 0.5 - mu) / sigma)
    if high is None and low is not None:
        return 1.0 - norm_cdf((low - 0.5 - mu) / sigma)
    if low is not None and high is not None:
        return norm_cdf((high + 0.5 - mu) / sigma) - norm_cdf((low - 0.5 - mu) / sigma)
    return 0.0


def parse_bucket(question: str) -> tuple[float | None, float | None, str]:
    q = question.lower()
    m = re.search(r"be (\d+)(?:°|º)?c or below", q)
    if m:
        return None, float(m.group(1)), "C"
    m = re.search(r"be (\d+)(?:°|º)?c or higher", q)
    if m:
        return float(m.group(1)), None, "C"
    m = re.search(r"be (\d+)(?:°|º)?c on", q)
    if m:
        t = float(m.group(1))
        return t, t, "C"
    m = re.search(r"be (\d+)(?:°|º)?f or below", q)
    if m:
        return None, float(m.group(1)), "F"
    m = re.search(r"be (\d+)(?:°|º)?f or higher", q)
    if m:
        return float(m.group(1)), None, "F"
    m = re.search(r"be (\d+)(?:°|º)?f on", q)
    if m:
        t = float(m.group(1))
        return t, t, "F"
    return None, None, "C"


def parse_city(question: str) -> str | None:
    m = re.search(r"temperature in ([a-z ]+?) on", question.lower())
    return m.group(1).strip() if m else None


def fetch_forecast_max(city: str) -> float | None:
    key = city.lower()
    if key not in CITY_COORDS:
        return None
    lat, lon, tz = CITY_COORDS[key]
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max&timezone={tz.replace('/', '%2F')}&forecast_days=1"
    )
    try:
        data = get_json(url)
        return float(data["daily"]["temperature_2m_max"][0])
    except (KeyError, IndexError, ValueError, TypeError):
        return None


def find_weather_events(limit: int = 8) -> list[dict[str, Any]]:
    data = get_json(f"{GAMMA}/public-search?q=highest+temperature&events_status=active")
    return (data.get("events") or [])[:limit]


def mark_positions(state: WeatherState) -> tuple[float, float]:
    """Return (positions_market_value, unrealized_pnl)."""
    value = 0.0
    cost = 0.0
    for pos in state.positions:
        try:
            m = get_json(f"{GAMMA}/markets/{pos.market_id}")
            prices = __import__("json").loads(m.get("outcomePrices", "[]"))
            no_price = float(prices[1]) if len(prices) > 1 else 1.0 - float(prices[0])
            value += pos.shares * no_price
            cost += pos.size_usd
        except Exception:
            value += pos.size_usd
            cost += pos.size_usd
    return value, value - cost


def run_cycle(state: WeatherState, stake_usd: float = 15.0) -> WeatherState:
    state.cycles += 1
    open_ids = {p.market_id for p in state.positions}

    for event in find_weather_events():
        for market in event.get("markets") or []:
            if market.get("closed") or not market.get("active", True):
                continue
            mid = str(market.get("id", ""))
            if mid in open_ids or len(state.positions) >= 6:
                continue

            question = market.get("question", "")
            city = parse_city(question)
            if not city:
                continue

            mu = fetch_forecast_max(city)
            if mu is None:
                continue

            low, high, unit = parse_bucket(question)
            if unit == "F":
                mu = mu * 9 / 5 + 32

            sigma = 1.2 if "September 2" in question or "on" in question.lower() else 2.0
            model_yes = bucket_prob(mu, sigma, low, high)
            prices = __import__("json").loads(market.get("outcomePrices", "[]") or "[]")
            if not prices:
                continue
            yes_p = float(prices[0])
            no_p = float(prices[1]) if len(prices) > 1 else 1.0 - yes_p

            edge = model_yes - yes_p
            if edge >= -0.08:
                continue
            if not (0.15 <= no_p <= 0.45):
                continue
            if state.bankroll < stake_usd:
                continue

            shares = stake_usd / no_p
            state.bankroll -= stake_usd
            state.positions.append(
                PaperPosition(
                    market_id=mid,
                    question=question[:80],
                    side="NO",
                    entry_price=no_p,
                    size_usd=stake_usd,
                    shares=shares,
                    model_yes=model_yes,
                    opened_at=datetime.now(timezone.utc).isoformat(),
                )
            )
            state.signals += 1
            state.log.append(
                f"BUY NO {city} bucket edge={edge:.2f} model={model_yes:.2f} mkt={yes_p:.2f} @ {no_p:.2f}"
            )
            open_ids.add(mid)

    pos_val, unreal = mark_positions(state)
    state.log.append(f"cycle={state.cycles} open={len(state.positions)} unrealized={unreal:+.2f}")
    return state


def state_dict(state: WeatherState) -> dict[str, Any]:
    pos_val, unreal = mark_positions(state)
    equity = state.bankroll + pos_val
    return {
        "strategy": "weather_edge",
        "starting_bankroll": state.starting_bankroll,
        "cash": round(state.bankroll, 2),
        "unrealized": round(unreal, 2),
        "equity": round(equity, 2),
        "net_pnl": round(equity - state.starting_bankroll, 2),
        "open_positions": len(state.positions),
        "signals": state.signals,
        "cycles": state.cycles,
        "positions": [p.__dict__ for p in state.positions],
        "recent_log": state.log[-10:],
    }
