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
python3 run_backtest.py
```

Results land in `results/` (`REPORT.md`, per-case JSON + trade CSVs).

## Caveats

- Yahoo Finance data (`NQ=F`, `EURUSD=X`), not broker MT5 ticks
- No spread / commission / slippage model
- M15 history limited to ~60 days on Yahoo; 2y runs use H1 entry proxy
- Not financial advice
