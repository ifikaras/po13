"""Paper ledger + cycle tests with a fake scanner."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from futures_bot.config import load_config
from futures_bot.paper import PaperLedger
from futures_bot.runner import run_cycle
from futures_bot.tests.test_approver import DEMO


class FakeScanner:
    def __init__(self, results):
        self.results = results

    def scan(self, payload, timeout=180.0):
        return {
            "status": "done",
            "scanned": len(self.results),
            "results": self.results,
            "use_confirmation": not payload.get("skip_confirmation"),
        }


class SilentNotifier:
    def __init__(self):
        self.messages = []

    def send(self, text: str) -> None:
        self.messages.append(text)


class PaperCycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger_path = Path(self.tmp.name) / "paper.json"

    def tearDown(self):
        self.tmp.cleanup()

    def _config(self):
        src = Path("config/futures_bot.yaml")
        cfg = load_config(src)
        # Point the ledger at the temp file without rewriting YAML.
        return cfg.__class__(
            scanner_url=cfg.scanner_url,
            mode=cfg.mode,
            scan=cfg.scan,
            approval=cfg.approval,
            risk=cfg.risk,
            notify=cfg.notify,
            ledger_path=self.ledger_path,
        )

    def test_cycle_opens_one_paper_order(self):
        config = self._config()
        notifier = SilentNotifier()
        result = run_cycle(
            config,
            client=FakeScanner([DEMO]),
            ledger=PaperLedger(self.ledger_path, config.risk.account_size),
            notifier=notifier,
            price_feed={},
        )
        self.assertEqual(len(result.approved), 1)
        self.assertEqual(result.approved[0]["symbol"], "DEMOUP")
        self.assertEqual(result.approved[0]["mode"], "paper")
        self.assertEqual(result.approved[0]["entry_type"], "limit")
        saved = json.loads(self.ledger_path.read_text())
        self.assertEqual(len(saved["positions"]), 1)
        self.assertEqual(saved["daily"]["new_positions"], 1)
        self.assertTrue(any("WOULD OPEN" in m for m in notifier.messages))

    def test_second_cycle_does_not_duplicate_symbol(self):
        config = self._config()
        ledger = PaperLedger(self.ledger_path, config.risk.account_size)
        run_cycle(config, client=FakeScanner([DEMO]), ledger=ledger, notifier=SilentNotifier(), price_feed={})
        ledger = PaperLedger(self.ledger_path, config.risk.account_size)
        result = run_cycle(
            config,
            client=FakeScanner([DEMO]),
            ledger=ledger,
            notifier=SilentNotifier(),
            price_feed={},
        )
        self.assertEqual(result.approved, [])
        self.assertEqual(len(result.skipped), 1)
        self.assertEqual(len(ledger.open_positions()), 1)

    def test_live_mode_rejected_by_config(self):
        path = Path(self.tmp.name) / "live.yaml"
        path.write_text("scanner_url: http://example\nmode: live\n")
        with self.assertRaises(ValueError):
            load_config(path)

    def test_scan_overrides_limit_and_skip_confirmation(self):
        config = self._config().with_scan_overrides(limit=20, skip_confirmation=True)
        payload = config.scan_payload()
        self.assertEqual(payload["limit"], 20)
        self.assertTrue(payload["skip_confirmation"])

    def test_reset_clears_open_positions(self):
        config = self._config()
        ledger = PaperLedger(self.ledger_path, config.risk.account_size)
        run_cycle(
            config,
            client=FakeScanner([DEMO]),
            ledger=ledger,
            notifier=SilentNotifier(),
            price_feed={},
        )
        self.assertEqual(len(ledger.open_positions()), 1)
        ledger.reset()
        self.assertFalse(self.ledger_path.exists())
        empty = PaperLedger(self.ledger_path, config.risk.account_size)
        self.assertEqual(empty.open_positions(), [])
        text = empty.status_text()
        self.assertIn("starting capital", text)
        self.assertIn("open: 0", text)


if __name__ == "__main__":
    unittest.main()
