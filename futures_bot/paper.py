"""JSON paper ledger. Records would-be orders without talking to an exchange."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class PaperLedger:
    def __init__(self, path: Path, account_size: float) -> None:
        self.path = path
        self.account_size = account_size
        self.data = self._load()

    def _empty(self) -> dict[str, Any]:
        return {
            "account_size": self.account_size,
            "mode": "paper",
            "positions": [],
            "orders": [],
            "rejects": [],
            "daily": {"date": _today(), "new_positions": 0},
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        raw = json.loads(self.path.read_text())
        if not isinstance(raw, dict):
            return self._empty()
        raw.setdefault("positions", [])
        raw.setdefault("orders", [])
        raw.setdefault("rejects", [])
        daily = raw.get("daily") or {}
        if daily.get("date") != _today():
            raw["daily"] = {"date": _today(), "new_positions": 0}
        return raw

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2) + "\n")

    def open_positions(self) -> list[dict[str, Any]]:
        return [p for p in self.data["positions"] if p.get("status") == "open"]

    def open_symbols(self) -> set[str]:
        return {str(p["symbol"]).upper() for p in self.open_positions()}

    def daily_new(self) -> int:
        return int(self.data["daily"].get("new_positions") or 0)

    def record_reject(self, symbol: str, reasons: tuple[str, ...]) -> dict[str, Any]:
        item = {
            "ts": _now(),
            "symbol": symbol,
            "reasons": list(reasons),
        }
        self.data["rejects"].append(item)
        return item

    def open_paper_order(self, *, symbol: str, row: dict[str, Any], decision: Any) -> dict[str, Any]:
        order = {
            "ts": _now(),
            "mode": "paper",
            "status": "open",
            "symbol": symbol,
            "name": row.get("name"),
            "side": "long",
            "entry_type": decision.entry_type,
            "planned_entry": decision.planned_entry,
            "market_entry": row.get("entry"),
            "optimal_entry": row.get("optimal_entry"),
            "stop_loss": row.get("stop_loss"),
            "take_profit_1": row.get("take_profit_1"),
            "take_profit_2": row.get("take_profit_2"),
            "quantity": decision.quantity,
            "notional": decision.notional,
            "risk_cash": decision.risk_cash,
            "score": row.get("total_score", row.get("score")),
            "conviction": row.get("conviction") or row.get("strength"),
            "reasons": list(decision.reasons),
        }
        self.data["orders"].append(order)
        self.data["positions"].append(dict(order))
        self.data["daily"]["new_positions"] = self.daily_new() + 1
        return order
