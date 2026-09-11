"""Public Binance USDT-M prices for paper mark-to-market. No API key."""

from __future__ import annotations

import json
import urllib.request


TICKER_URL = "https://fapi.binance.com/fapi/v1/ticker/price"


def to_binance_symbol(symbol: str) -> str:
    text = str(symbol or "").upper().replace("/", "").replace("-", "")
    if not text:
        return ""
    if text.endswith("USDT") or text.endswith("BUSD") or text.endswith("USDC"):
        return text
    return text + "USDT"


def fetch_mark_prices(symbols: list[str] | None = None) -> dict[str, float]:
    req = urllib.request.Request(TICKER_URL, headers={"User-Agent": "po13-futures-paper"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        rows = json.loads(resp.read().decode("utf-8"))
    all_px = {str(row["symbol"]).upper(): float(row["price"]) for row in rows if "symbol" in row}
    if not symbols:
        return all_px
    out: dict[str, float] = {}
    for raw in symbols:
        bsym = to_binance_symbol(raw)
        if bsym in all_px:
            out[str(raw).upper()] = all_px[bsym]
            out[bsym] = all_px[bsym]
    return out
