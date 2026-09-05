# CRT Strategy Backtest Results

## Rules tested
- CRT range = previous closed **H4** candle
- Entry on **M15** (exact) or **H1** (long-history proxy)
- Sweep high/low → close back inside range → candle color confirm
- SL beyond sweep + 0.1×ATR(H4)
- TP1 = mid (50%, BE on remainder), TP2 = opposite side
- Min RR to TP2 = 1.5, max SL = 3×ATR, 1 trade per CRT range
- Session 07:00–21:00 UTC (unless noted)
- Same-bar SL/TP conflict counted as **SL** (conservative)
- Data: Yahoo Finance (`NQ=F`, `EURUSD=X`)

## Results

### US100/NQ H4+M15 strict (60d)
- Period: 2026-06-26 04:00:00+00:00 → 2026-09-04 20:45:00+00:00
- Trades: 72 (L 36 / S 36)
- Win rate: 43.1% (31W / 41L)
- Total R: +5.48R
- Avg R / trade: +0.076R
- Profit factor: 1.13
- Max DD: -11.04R
- Best / Worst: +4.27R / -1.00R

### EURUSD H4+M15 strict (60d)
- Period: 2026-06-14 23:00:00+00:00 → 2026-09-04 21:15:00+00:00
- Trades: 58 (L 35 / S 23)
- Win rate: 51.7% (30W / 28L)
- Total R: +16.94R
- Avg R / trade: +0.292R
- Profit factor: 1.61
- Max DD: -4.26R
- Best / Worst: +5.25R / -1.00R

### US100/NQ H4+H1 proxy (2y)
- Period: 2024-09-05 00:00:00+00:00 → 2026-09-04 20:00:00+00:00
- Trades: 316 (L 116 / S 200)
- Win rate: 49.4% (156W / 160L)
- Total R: +11.14R
- Avg R / trade: +0.035R
- Profit factor: 1.07
- Max DD: -21.30R
- Best / Worst: +5.00R / -1.00R

### EURUSD H4+H1 proxy (2y)
- Period: 2024-09-04 23:00:00+00:00 → 2026-09-04 21:00:00+00:00
- Trades: 289 (L 143 / S 146)
- Win rate: 50.9% (147W / 142L)
- Total R: +1.73R
- Avg R / trade: +0.006R
- Profit factor: 1.01
- Max DD: -15.54R
- Best / Worst: +6.41R / -1.00R

### US100/NQ H4+H1 NO color confirm (2y)
- Period: 2024-09-05 00:00:00+00:00 → 2026-09-04 20:00:00+00:00
- Trades: 586 (L 244 / S 342)
- Win rate: 41.0% (240W / 346L)
- Total R: -43.11R
- Avg R / trade: -0.074R
- Profit factor: 0.88
- Max DD: -49.99R
- Best / Worst: +5.70R / -1.00R

### US100/NQ H4+H1 no session filter (2y)
- Period: 2024-09-05 00:00:00+00:00 → 2026-09-04 20:00:00+00:00
- Trades: 470 (L 180 / S 290)
- Win rate: 46.8% (220W / 250L)
- Total R: -15.09R
- Avg R / trade: -0.032R
- Profit factor: 0.94
- Max DD: -33.05R
- Best / Worst: +5.00R / -1.00R

## Notes
- M15 history is limited by Yahoo (~60 days); H1 proxy covers ~2 years.
- This is CFD/futures proxy data, not broker MT5 ticks — spreads/slippage not modeled.
- Not financial advice; educational backtest only.
