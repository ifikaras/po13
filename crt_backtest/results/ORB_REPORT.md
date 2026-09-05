# US100/NQ Opening Range Breakout Backtest

## Rules
- OR = first 15m / 30m / 60m of NY RTH 09:30
- Breakout stop entry; SL = opposite OR side
- Daily SMA200 bias (long only above / short only below)
- Skip if OR width outside 0.10–0.80 × daily ATR(14)
- TP1=1R (50% + BE), TP2=2R; flatten at RTH close
- Cost 1.5 bps RT; daily features warmed from max daily history

## Data limits
- Yahoo 5m/15m ≈ 60 calendar days
- 1h first-hour OR proxy ≈ 2 years (coarser OR)

## Results

### NQ ORB15 +bias 60d
- Period: 2026-06-26 → 2026-09-04
- Trades: 38 (L 38 / S 0)
- Win rate: 39.5% (15W / 23L)
- Total R: -11.25R | avg -0.296R | PF 0.47 | DD -12.59R
- Best / Worst: +1.48R / -1.05R
- Yearly R: 2026:-11.3

### NQ ORB15 no-bias 60d
- Period: 2026-06-26 → 2026-09-04
- Trades: 50 (L 28 / S 22)
- Win rate: 50.0% (25W / 25L)
- Total R: -6.82R | avg -0.136R | PF 0.72 | DD -8.10R
- Best / Worst: +1.48R / -1.05R
- Yearly R: 2026:-6.8

### NQ ORB30 +bias 60d
- Period: 2026-06-26 → 2026-09-04
- Trades: 33 (L 33 / S 0)
- Win rate: 48.5% (16W / 17L)
- Total R: -3.99R | avg -0.121R | PF 0.66 | DD -6.64R
- Best / Worst: +1.12R / -1.05R
- Yearly R: 2026:-4.0

### NQ ORB15 on5m +bias 60d
- Period: 2026-06-26 → 2026-09-04
- Trades: 38 (L 38 / S 0)
- Win rate: 36.8% (14W / 24L)
- Total R: -12.96R | avg -0.341R | PF 0.42 | DD -14.30R
- Best / Worst: +1.48R / -1.05R
- Yearly R: 2026:-13.0

### NQ ORB60 1h-proxy +bias 2y
- Period: 2024-09-04 → 2026-09-04
- Trades: 333 (L 296 / S 37)
- Win rate: 52.0% (173W / 160L)
- Total R: +0.25R | avg +0.001R | PF 1.00 | DD -11.35R
- Best / Worst: +1.49R / -1.08R
- Yearly R: 2024:+4.0, 2025:-0.7, 2026:-3.0

### NQ ORB60 1h-proxy no-bias 2y
- Period: 2024-09-04 → 2026-09-04
- Trades: 470 (L 281 / S 189)
- Win rate: 50.4% (237W / 233L)
- Total R: -5.12R | avg -0.011R | PF 0.97 | DD -15.77R
- Best / Worst: +1.49R / -1.08R
- Yearly R: 2024:+3.4, 2025:+1.6, 2026:-10.2

### NQ ORB60 1h-proxy +bias long-only 2y
- Period: 2024-09-04 → 2026-09-04
- Trades: 296 (L 296 / S 0)
- Win rate: 51.0% (151W / 145L)
- Total R: -3.45R | avg -0.012R | PF 0.96 | DD -11.40R
- Best / Worst: +1.48R / -1.08R
- Yearly R: 2024:+4.0, 2025:-2.1, 2026:-5.3

### NQ ORB60 1h-proxy +bias looseWidth 2y
- Period: 2024-09-04 → 2026-09-04
- Trades: 340 (L 301 / S 39)
- Win rate: 51.8% (176W / 164L)
- Total R: +0.78R | avg +0.002R | PF 1.01 | DD -11.30R
- Best / Worst: +1.49R / -1.08R
- Yearly R: 2024:+4.0, 2025:-0.4, 2026:-2.8

## Reading guide
- 60d samples are tiny — directional only.
- 2y 1h proxy has more trades but coarser OR definition.
- Weak/negative after costs ⇒ not EA-ready without extra filters (news, OR quality, VWAP).

Not financial advice.
