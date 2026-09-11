"""JSON paper ledger. Records would-be orders without talking to an exchange."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from futures_bot.prices import to_binance_symbol


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _money(value: float) -> str:
    return f"${value:+,.2f}"


class PaperLedger:
    def __init__(self, path: Path, account_size: float) -> None:
        self.path = path
        self.account_size = account_size
        self.data = self._load()

    def _empty(self) -> dict[str, Any]:
        return {
            "account_size": self.account_size,
            "starting_capital": self.account_size,
            "mode": "paper",
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "equity": self.account_size,
            "wins": 0,
            "losses": 0,
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
        raw.setdefault("starting_capital", raw.get("account_size") or self.account_size)
        raw.setdefault("realized_pnl", 0.0)
        raw.setdefault("unrealized_pnl", 0.0)
        raw.setdefault("wins", 0)
        raw.setdefault("losses", 0)
        daily = raw.get("daily") or {}
        if daily.get("date") != _today():
            raw["daily"] = {"date": _today(), "new_positions": 0}
        for pos in raw["positions"]:
            self._migrate_position(pos)
        self._refresh_totals(raw)
        return raw

    def _migrate_position(self, pos: dict[str, Any]) -> None:
        if pos.get("status") == "closed":
            pos.setdefault("filled", True)
            return
        if "filled" in pos:
            if not pos["filled"] and pos.get("status") == "open":
                pos["status"] = "waiting"
            return
        if pos.get("entry_type") == "market":
            pos["filled"] = True
            pos["fill_price"] = pos.get("fill_price") or pos.get("planned_entry")
            pos["fill_ts"] = pos.get("fill_ts") or pos.get("ts")
            pos["status"] = "open"
        else:
            pos["filled"] = False
            pos["status"] = "waiting"

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2) + "\n")

    def active_positions(self) -> list[dict[str, Any]]:
        return [p for p in self.data["positions"] if p.get("status") in {"open", "waiting"}]

    def open_positions(self) -> list[dict[str, Any]]:
        return self.active_positions()

    def filled_positions(self) -> list[dict[str, Any]]:
        return [p for p in self.data["positions"] if p.get("status") == "open" and p.get("filled")]

    def waiting_positions(self) -> list[dict[str, Any]]:
        return [p for p in self.data["positions"] if p.get("status") == "waiting"]

    def closed_positions(self) -> list[dict[str, Any]]:
        return [p for p in self.data["positions"] if p.get("status") == "closed"]

    def open_symbols(self) -> set[str]:
        return {str(p["symbol"]).upper() for p in self.active_positions()}

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
        market = decision.entry_type == "market"
        order = {
            "ts": _now(),
            "mode": "paper",
            "status": "open" if market else "waiting",
            "filled": market,
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
            "unrealized_pnl": 0.0,
        }
        if market:
            order["fill_price"] = decision.planned_entry
            order["fill_ts"] = order["ts"]
        self.data["orders"].append(dict(order))
        self.data["positions"].append(order)
        self.data["daily"]["new_positions"] = self.daily_new() + 1
        return order

    def reset(self) -> None:
        self.data = self._empty()
        if self.path.exists():
            self.path.unlink()

    def _lookup_price(self, prices: dict[str, float], symbol: str) -> float | None:
        raw = str(symbol or "").upper()
        bsym = to_binance_symbol(raw)
        for key in (raw, bsym, raw.replace("USDT", "")):
            if key and key in prices:
                return float(prices[key])
        return None

    def _fill(self, pos: dict[str, Any], price: float) -> None:
        pos["filled"] = True
        pos["fill_price"] = price
        pos["fill_ts"] = _now()
        pos["status"] = "open"

    def _close(self, pos: dict[str, Any], price: float, reason: str) -> float:
        qty = float(pos["quantity"])
        entry = float(pos.get("fill_price") or pos["planned_entry"])
        pnl = (price - entry) * qty
        pos["status"] = "closed"
        pos["filled"] = True
        pos["close_price"] = price
        pos["close_ts"] = _now()
        pos["close_reason"] = reason
        pos["realized_pnl"] = pnl
        pos["unrealized_pnl"] = 0.0
        self.data["realized_pnl"] = float(self.data.get("realized_pnl") or 0) + pnl
        if pnl >= 0:
            self.data["wins"] = int(self.data.get("wins") or 0) + 1
        else:
            self.data["losses"] = int(self.data.get("losses") or 0) + 1
        return pnl

    def _refresh_totals(self, data: dict[str, Any] | None = None) -> None:
        blob = data if data is not None else self.data
        unreal = 0.0
        for pos in blob.get("positions") or []:
            if pos.get("status") == "open" and pos.get("filled"):
                unreal += float(pos.get("unrealized_pnl") or 0)
        blob["unrealized_pnl"] = unreal
        start = float(blob.get("starting_capital") or blob.get("account_size") or self.account_size)
        blob["starting_capital"] = start
        blob["equity"] = start + float(blob.get("realized_pnl") or 0) + unreal

    def mark_to_market(self, prices: dict[str, float]) -> list[str]:
        events: list[str] = []
        for pos in self.data["positions"]:
            if pos.get("status") == "closed":
                continue
            px = self._lookup_price(prices, str(pos.get("symbol") or ""))
            if px is None:
                continue
            pos["mark"] = px
            pos["mark_ts"] = _now()
            planned = float(pos.get("planned_entry") or 0)
            if not pos.get("filled"):
                if pos.get("entry_type") == "market":
                    self._fill(pos, planned or px)
                    events.append(f"FILL {pos['symbol']} market @ {pos['fill_price']}")
                elif planned and px <= planned:
                    self._fill(pos, planned)
                    events.append(f"FILL {pos['symbol']} limit @ {planned}")
                else:
                    pos["unrealized_pnl"] = 0.0
                    continue
            entry = float(pos.get("fill_price") or planned)
            qty = float(pos.get("quantity") or 0)
            sl = pos.get("stop_loss")
            tp1 = pos.get("take_profit_1")
            if sl is not None and px <= float(sl):
                pnl = self._close(pos, float(sl), "stop_loss")
                events.append(f"CLOSE {pos['symbol']} STOP { _money(pnl) }")
                continue
            if tp1 is not None and px >= float(tp1):
                pnl = self._close(pos, float(tp1), "take_profit_1")
                events.append(f"CLOSE {pos['symbol']} TP1 { _money(pnl) }")
                continue
            pos["unrealized_pnl"] = (px - entry) * qty
            pos["status"] = "open"
        self._refresh_totals()
        return events

    def status_text(self) -> str:
        self._refresh_totals()
        start = float(self.data.get("starting_capital") or self.account_size)
        realized = float(self.data.get("realized_pnl") or 0)
        unreal = float(self.data.get("unrealized_pnl") or 0)
        equity = float(self.data.get("equity") or start)
        wins = int(self.data.get("wins") or 0)
        losses = int(self.data.get("losses") or 0)
        lines = [
            f"starting capital: ${start:,.2f}",
            f"realized PnL: {_money(realized)}  ({wins}W / {losses}L)",
            f"open PnL: {_money(unreal)}",
            f"equity: ${equity:,.2f}",
        ]
        waiting = self.waiting_positions()
        opened = self.filled_positions()
        lines.append(f"waiting limits: {len(waiting)}")
        for pos in waiting:
            lines.append(
                f"  {pos.get('symbol')} WAIT limit @ {pos.get('planned_entry')} "
                f"(mark {pos.get('mark', 'n/a')}) SL={pos.get('stop_loss')} TP1={pos.get('take_profit_1')}"
            )
        lines.append(f"open: {len(opened)}")
        for pos in opened:
            lines.append(
                f"  {pos.get('symbol')} LONG fill @ {pos.get('fill_price')} mark={pos.get('mark', 'n/a')} "
                f"uPnL={_money(float(pos.get('unrealized_pnl') or 0))} "
                f"SL={pos.get('stop_loss')} TP1={pos.get('take_profit_1')}"
            )
        closed = self.closed_positions()[-8:]
        lines.append(f"closed: {len(self.closed_positions())}")
        for pos in closed:
            lines.append(
                f"  {pos.get('symbol')} {pos.get('close_reason')} {_money(float(pos.get('realized_pnl') or 0))} "
                f"({pos.get('fill_price')} -> {pos.get('close_price')})"
            )
        return "\n".join(lines)
