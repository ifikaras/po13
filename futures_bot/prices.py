"""Mark prices for paper PnL. Prefer Binance USDT-M; fall back to the scanner."""

from __future__ import annotations

import json
import urllib.error
import urllib.request


TICKER_URL = "https://fapi.binance.com/fapi/v1/ticker/price"


def to_binance_symbol(symbol: str) -> str:
    text = str(symbol or "").upper().replace("/", "").replace("-", "")
    if not text:
        return ""
    if text.endswith("USDT") or text.endswith("BUSD") or text.endswith("USDC"):
        return text
    return text + "USDT"


def _http_json(url: str, payload: dict | None = None, timeout: float = 20.0):
    data = None
    headers = {"User-Agent": "po13-futures-paper", "Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_binance_prices() -> dict[str, float]:
    rows = _http_json(TICKER_URL)
    return {str(row["symbol"]).upper(): float(row["price"]) for row in rows if "symbol" in row}


def fetch_scanner_prices(scanner_url: str, symbols: list[str]) -> dict[str, float]:
    base = scanner_url.rstrip("/")
    out: dict[str, float] = {}
    for raw in symbols:
        if not raw:
            continue
        body = _http_json(
            f"{base}/api/analyze",
            {"symbol": raw, "skip_confirmation": True},
            timeout=45.0,
        )
        row = body.get("result") or body
        entry = row.get("entry")
        if entry is None:
            continue
        price = float(entry)
        key = str(raw).upper()
        out[key] = price
        out[to_binance_symbol(key)] = price
    return out


def fetch_mark_prices(
    symbols: list[str] | None = None,
    scanner_url: str | None = None,
) -> dict[str, float]:
    wanted = [str(s).upper() for s in (symbols or []) if s]
    try:
        all_px = fetch_binance_prices()
        if not wanted:
            return all_px
        out: dict[str, float] = {}
        for raw in wanted:
            bsym = to_binance_symbol(raw)
            if bsym in all_px:
                out[raw] = all_px[bsym]
                out[bsym] = all_px[bsym]
        return out
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, KeyError):
        if not scanner_url or not wanted:
            raise
        return fetch_scanner_prices(scanner_url, wanted)
