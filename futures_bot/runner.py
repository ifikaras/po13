"""One scan cycle: fetch signals, apply approval rules, record paper orders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from futures_bot.approver import decide
from futures_bot.config import BotConfig
from futures_bot.notify import Notifier
from futures_bot.paper import PaperLedger
from futures_bot.prices import fetch_mark_prices
from futures_bot.scanner_client import ScannerClient


@dataclass
class CycleResult:
    scanned: int = 0
    setups: int = 0
    approved: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)
    marks: list[str] = field(default_factory=list)
    job: dict[str, Any] = field(default_factory=dict)


def run_cycle(
    config: BotConfig,
    *,
    client: ScannerClient | None = None,
    ledger: PaperLedger | None = None,
    notifier: Notifier | None = None,
    self_test: bool | None = None,
    price_feed: Any = None,
) -> CycleResult:
    client = client or ScannerClient(config.scanner_url)
    ledger = ledger or PaperLedger(config.ledger_path, config.risk.account_size)
    notifier = notifier or Notifier(config.notify)

    job = client.scan(config.scan_payload(self_test=self_test))
    results = list(job.get("results") or [])
    out = CycleResult(scanned=int(job.get("scanned") or len(results)), setups=len(results), job=job)

    notifier.send(
        f"[paper] scan done: {out.scanned} symbols, {out.setups} setups "
        f"(confirmation={'on' if job.get('use_confirmation') else 'off'})"
    )

    open_symbols = ledger.open_symbols()
    open_count = len(ledger.open_positions())
    daily_new = ledger.daily_new()

    for row in results:
        symbol = str(row.get("symbol") or "?").upper()
        decision = decide(
            row,
            config.approval,
            config.risk,
            open_symbols=open_symbols,
            open_count=open_count,
            daily_new=daily_new,
        )
        if not decision.approved:
            item = ledger.record_reject(symbol, decision.reasons)
            out.skipped.append(item)
            notifier.send(f"[paper] SKIP {symbol}: {'; '.join(decision.reasons)}")
            continue
        order = ledger.open_paper_order(symbol=symbol, row=row, decision=decision)
        out.approved.append(order)
        open_symbols.add(symbol)
        open_count += 1
        daily_new += 1
        notifier.send(f"[paper] WOULD OPEN {decision.summary}")

    symbols = [str(p.get("symbol") or "") for p in ledger.active_positions()]
    try:
        if price_feed is None:
            prices = fetch_mark_prices(symbols, scanner_url=config.scanner_url)
        elif callable(price_feed):
            prices = price_feed(symbols)
        else:
            prices = dict(price_feed)
        out.marks = ledger.mark_to_market(prices)
    except Exception as exc:  # noqa: BLE001 - paper loop must survive a dead ticker
        notifier.send(f"[paper] price fetch failed: {exc}")
        out.marks = []
    for event in out.marks:
        notifier.send(f"[paper] {event}")

    ledger.save()
    if not out.approved and not out.skipped:
        notifier.send("[paper] no setups this run")
    return out
