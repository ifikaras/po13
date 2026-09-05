# CRT Daily-Only Backtest (3–5 years)

## Rules
- CRT range = **previous closed Daily candle**
- Entry = same Daily TF (sweep + close back inside + color confirm)
- No session filter (not meaningful on D1)
- SL beyond sweep + 0.1×ATR(D1); TP1 mid / TP2 opposite side
- Default min RR to TP2 = 1.5 (plus looser RR=1.0 ablation)
- Data: Yahoo Finance daily (`NQ=F`, `EURUSD=X`)

## Results

### US100/NQ D1 strict (4y)
- Period: 2022-09-06 00:00:00+00:00 → 2026-09-04 00:00:00+00:00
- Trades: 40 (L 10 / S 30)
- Win rate: 57.5% (23W / 17L)
- Total R: +8.33R
- Avg R / trade: +0.208R
- Profit factor: 1.49
- Max DD: -7.70R
- Best / Worst: +3.70R / -1.00R

### EURUSD D1 strict (4y)
- Period: 2022-09-05 00:00:00+00:00 → 2026-09-04 00:00:00+00:00
- Trades: 12 (L 4 / S 8)
- Win rate: 83.3% (10W / 2L)
- Total R: +11.25R
- Avg R / trade: +0.938R
- Profit factor: 12.25
- Max DD: -1.00R
- Best / Worst: +2.33R / -1.00R

### US100/NQ D1 strict (5y)
- Period: 2021-09-07 00:00:00+00:00 → 2026-09-04 00:00:00+00:00
- Trades: 48 (L 15 / S 33)
- Win rate: 54.2% (26W / 22L)
- Total R: +6.50R
- Avg R / trade: +0.135R
- Profit factor: 1.30
- Max DD: -7.70R
- Best / Worst: +3.70R / -1.00R

### EURUSD D1 strict (5y)
- Period: 2021-09-06 00:00:00+00:00 → 2026-09-04 00:00:00+00:00
- Trades: 17 (L 8 / S 9)
- Win rate: 88.2% (15W / 2L)
- Total R: +18.87R
- Avg R / trade: +1.110R
- Profit factor: 19.87
- Max DD: -1.00R
- Best / Worst: +2.87R / -1.00R

### US100/NQ D1 NO color confirm (4y)
- Period: 2022-09-06 00:00:00+00:00 → 2026-09-04 00:00:00+00:00
- Trades: 117 (L 40 / S 77)
- Win rate: 38.5% (45W / 72L)
- Total R: -16.40R
- Avg R / trade: -0.140R
- Profit factor: 0.77
- Max DD: -22.73R
- Best / Worst: +3.70R / -1.00R

### US100/NQ D1 minRR=1.0 (4y)
- Period: 2022-09-06 00:00:00+00:00 → 2026-09-04 00:00:00+00:00
- Trades: 65 (L 21 / S 44)
- Win rate: 50.8% (33W / 32L)
- Total R: -0.29R
- Avg R / trade: -0.004R
- Profit factor: 0.99
- Max DD: -15.12R
- Best / Worst: +3.70R / -1.00R

### EURUSD D1 minRR=1.0 (4y)
- Period: 2022-09-05 00:00:00+00:00 → 2026-09-04 00:00:00+00:00
- Trades: 19 (L 8 / S 11)
- Win rate: 73.7% (14W / 5L)
- Total R: +10.25R
- Avg R / trade: +0.539R
- Profit factor: 3.56
- Max DD: -1.32R
- Best / Worst: +2.33R / -1.00R

## Interpretation notes
- D1 CRT produces far fewer trades than H4/M15.
- Same-bar SL/TP conflicts counted as SL (conservative).
- No spread/slippage; not broker MT5 data.
- Not financial advice.
