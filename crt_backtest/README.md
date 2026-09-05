# CRT backtest (Python proxy for MQL5 rules)

Educational backtest of the Candle Range Theory rules discussed for an MQL5 EA.

## Strategy

- **Range TF:** previous closed H4 candle (high / low / mid)
- **Entry TF:** M15 (exact) or H1 (longer-history proxy)
- Sweep of range high/low → close back inside → candle color confirm
- SL beyond sweep extreme + 0.1×ATR(H4)
- TP1 = mid (50%, remainder to BE), TP2 = opposite side
- Min RR 1.5 to TP2, max SL 3×ATR, one trade per CRT range
- Session filter 07:00–21:00 UTC

## Run

```bash
pip install pandas numpy yfinance
cd crt_backtest
python3 run_backtest.py              # CRT H4 + M15/H1
python3 run_daily_backtest.py        # CRT Daily-only, 4–5y
python3 run_breakout_backtest.py     # Donchian/ATR D1 breakout (max history)
```

Results land in `results/` (`REPORT.md`, `DAILY_REPORT.md`, `BREAKOUT_REPORT.md`, per-case JSON + trade CSVs).

## Recommended EA candidate (not CRT)

Daily Donchian breakout + ATR stops (see `breakout_strategy.py`):

1. Signal on D1 close, fill next open
2. Entry: close breaks prior 20-day Donchian high/low
3. Filter: SMA200 (longs above / shorts below)
4. Stop: 2×ATR(20); trail 3×ATR chandelier; also exit on 10-day Donchian
5. Prefer **US100 long-only** or **Gold L/S** — EURUSD failed this ruleset

## Caveats

- Yahoo Finance data (`NQ=F`, `EURUSD=X`), not broker MT5 ticks
- No spread / commission / slippage model
- M15 history limited to ~60 days on Yahoo; 2y runs use H1 entry proxy
- Not financial advice
