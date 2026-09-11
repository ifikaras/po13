"""Price helper unit tests. No network."""

from __future__ import annotations

import unittest

from futures_bot.prices import to_binance_symbol


class PriceHelperTests(unittest.TestCase):
    def test_appends_usdt(self):
        self.assertEqual(to_binance_symbol("NEAR"), "NEARUSDT")
        self.assertEqual(to_binance_symbol("ltcusdt"), "LTCUSDT")
        self.assertEqual(to_binance_symbol("XMR/USDT"), "XMRUSDT")


if __name__ == "__main__":
    unittest.main()
