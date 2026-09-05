# Mean-Reversion Candidates vs Buy&Hold

Goal: find rules that are **not just riding a bull**.

## Strategies
1. **RSI(2) dip-buy** (Connors-style): RSI2≤10 & Close>SMA200 → buy next open; exit RSI2≥70; SL 2×ATR
2. **Bollinger fade**: fade BB(20,2) to mid; optional ADX<25; SL 2×ATR; long/short

## Results

### US100/NQ RSI2≤10 dip-buy 5y
- Period: 2021-09-07 → 2026-09-04
- Trades: 44 (L 44 / S 0)
- Win rate: 75.0% (33W / 11L)
- Strategy: +6.10R | avg +0.139R | PF 1.66 | DD -3.20R | bars 3.0
- Buy&Hold: +88.6% ≈ +42.47R
- Strategy − B&H: -36.38R
- Yearly R: 2021:+0.4, 2022:-0.9, 2023:-1.3, 2024:+4.0, 2025:+2.0, 2026:+1.9

### US100/NQ RSI2≤5 dip-buy 5y
- Period: 2021-09-07 → 2026-09-04
- Trades: 26 (L 26 / S 0)
- Win rate: 76.9% (20W / 6L)
- Strategy: +4.70R | avg +0.181R | PF 1.87 | DD -3.11R | bars 2.7
- Buy&Hold: +88.6% ≈ +42.47R
- Strategy − B&H: -37.77R
- Yearly R: 2021:+1.1, 2022:+0.4, 2023:-1.7, 2024:+0.8, 2025:+0.5, 2026:+3.6

### SPX RSI2≤10 dip-buy 5y
- Period: 2021-09-07 → 2026-09-04
- Trades: 49 (L 49 / S 0)
- Win rate: 69.4% (34W / 15L)
- Strategy: +5.30R | avg +0.108R | PF 1.37 | DD -3.30R | bars 2.8
- Buy&Hold: +70.8% ≈ +53.66R
- Strategy − B&H: -48.36R
- Yearly R: 2021:-0.7, 2022:-2.0, 2023:+1.4, 2024:+4.1, 2025:+2.1, 2026:+0.4

### SPX RSI2≤5 dip-buy 5y
- Period: 2021-09-07 → 2026-09-04
- Trades: 26 (L 26 / S 0)
- Win rate: 76.9% (20W / 6L)
- Strategy: +8.84R | avg +0.340R | PF 2.72 | DD -1.09R | bars 2.7
- Buy&Hold: +70.8% ≈ +53.66R
- Strategy − B&H: -44.82R
- Yearly R: 2021:-0.1, 2022:-0.4, 2023:+0.9, 2024:+4.3, 2025:+2.4, 2026:+1.8

### Gold RSI2≤10 dip-buy 5y
- Period: 2021-09-07 → 2026-09-04
- Trades: 32 (L 32 / S 0)
- Win rate: 65.6% (21W / 11L)
- Strategy: +1.18R | avg +0.037R | PF 1.12 | DD -5.00R | bars 4.0
- Buy&Hold: +149.3% ≈ +81.75R
- Strategy − B&H: -80.56R
- Yearly R: 2021:-0.3, 2022:-2.0, 2023:-1.4, 2024:+1.0, 2025:+3.4, 2026:+0.5

### Gold RSI2≤5 dip-buy 5y
- Period: 2021-09-07 → 2026-09-04
- Trades: 21 (L 21 / S 0)
- Win rate: 61.9% (13W / 8L)
- Strategy: +1.51R | avg +0.072R | PF 1.25 | DD -2.03R | bars 4.3
- Buy&Hold: +149.3% ≈ +81.75R
- Strategy − B&H: -80.24R
- Yearly R: 2021:-0.3, 2022:-1.0, 2023:-0.3, 2024:+1.7, 2025:+1.4, 2026:-0.0

### EURUSD BB fade +ADX 5y
- Period: 2021-09-06 → 2026-09-04
- Trades: 39 (L 19 / S 20)
- Win rate: 51.3% (20W / 19L)
- Strategy: +0.94R | avg +0.024R | PF 1.05 | DD -5.12R | bars 13.6
- Buy&Hold: -2.2% ≈ -2.45R
- Strategy − B&H: +3.39R
- Yearly R: 2021:-2.0, 2022:+0.6, 2023:-0.4, 2024:+3.0, 2025:+0.8, 2026:-1.1

### EURUSD BB fade noADX 5y
- Period: 2021-09-06 → 2026-09-04
- Trades: 50 (L 27 / S 23)
- Win rate: 50.0% (25W / 25L)
- Strategy: +0.47R | avg +0.009R | PF 1.02 | DD -8.15R | bars 16.4
- Buy&Hold: -2.2% ≈ -2.45R
- Strategy − B&H: +2.92R
- Yearly R: 2021:-2.0, 2022:-1.3, 2023:-1.5, 2024:+2.0, 2025:-0.1, 2026:+3.4

### GBPUSD BB fade +ADX 5y
- Period: 2021-09-06 → 2026-09-04
- Trades: 37 (L 19 / S 18)
- Win rate: 48.6% (18W / 19L)
- Strategy: -2.67R | avg -0.072R | PF 0.86 | DD -5.05R | bars 10.4
- Buy&Hold: -2.5% ≈ -2.02R
- Strategy − B&H: -0.66R
- Yearly R: 2021:-0.9, 2022:-3.3, 2023:+0.6, 2024:+3.4, 2025:-2.6, 2026:+0.1

### GBPUSD BB fade noADX 5y
- Period: 2021-09-06 → 2026-09-04
- Trades: 57 (L 31 / S 26)
- Win rate: 52.6% (30W / 27L)
- Strategy: +1.91R | avg +0.033R | PF 1.07 | DD -8.25R | bars 11.3
- Buy&Hold: -2.5% ≈ -2.02R
- Strategy − B&H: +3.92R
- Yearly R: 2021:-0.9, 2022:-5.9, 2023:+3.2, 2024:+3.2, 2025:-0.1, 2026:+2.3

### USDJPY BB fade +ADX 5y
- Period: 2021-09-06 → 2026-09-04
- Trades: 32 (L 9 / S 23)
- Win rate: 56.2% (18W / 14L)
- Strategy: +2.04R | avg +0.064R | PF 1.14 | DD -4.21R | bars 8.9
- Buy&Hold: +42.3% ≈ +53.57R
- Strategy − B&H: -51.53R
- Yearly R: 2021:+0.5, 2022:-2.0, 2023:-1.9, 2024:+4.9, 2025:-1.0, 2026:+1.5

### USDJPY BB fade noADX 5y
- Period: 2021-09-06 → 2026-09-04
- Trades: 57 (L 20 / S 37)
- Win rate: 45.6% (26W / 31L)
- Strategy: -4.28R | avg -0.075R | PF 0.86 | DD -8.18R | bars 12.3
- Buy&Hold: +42.3% ≈ +53.57R
- Strategy − B&H: -57.86R
- Yearly R: 2021:-0.7, 2022:-5.7, 2023:+0.7, 2024:+1.7, 2025:-3.4, 2026:+3.1

### AUDUSD BB fade +ADX 5y
- Period: 2021-09-06 → 2026-09-04
- Trades: 37 (L 18 / S 19)
- Win rate: 64.9% (24W / 13L)
- Strategy: +7.49R | avg +0.202R | PF 1.59 | DD -3.41R | bars 10.9
- Buy&Hold: -3.2% ≈ -1.41R
- Strategy − B&H: +8.90R
- Yearly R: 2021:+0.9, 2022:-0.2, 2023:+0.6, 2024:+2.7, 2025:+4.6, 2026:-1.1

### AUDUSD BB fade noADX 5y
- Period: 2021-09-06 → 2026-09-04
- Trades: 45 (L 22 / S 23)
- Win rate: 57.8% (26W / 19L)
- Strategy: +5.06R | avg +0.112R | PF 1.27 | DD -3.90R | bars 14.2
- Buy&Hold: -3.2% ≈ -1.41R
- Strategy − B&H: +6.47R
- Yearly R: 2021:+2.4, 2022:-0.6, 2023:+0.5, 2024:-0.5, 2025:+4.6, 2026:-1.3

### EURUSD BB fade +ADX MAX
- Period: 2005-01-04 → 2026-09-04
- Trades: 159 (L 82 / S 77)
- Win rate: 52.2% (83W / 76L)
- Strategy: -0.72R | avg -0.005R | PF 0.99 | DD -8.07R | bars 12.2
- Buy&Hold: -12.5% ≈ -7.26R
- Strategy − B&H: +6.54R
- Yearly R: 2005:-1.2, 2006:-1.4, 2007:-0.9, 2008:+2.0, 2009:-0.8, 2010:-0.2, 2011:+1.2, 2012:-3.6, 2013:+0.6, 2014:+0.0, 2015:-2.6, 2016:+2.3, 2017:+0.9, 2018:-2.0, 2019:+8.1, 2020:-2.0, 2021:-4.2, 2022:+0.6, 2023:-0.4, 2024:+3.0, 2025:+0.8, 2026:-1.1

### EURUSD BB fade noADX MAX
- Period: 2005-01-04 → 2026-09-04
- Trades: 219 (L 110 / S 109)
- Win rate: 48.9% (107W / 112L)
- Strategy: -13.45R | avg -0.061R | PF 0.88 | DD -21.78R | bars 13.4
- Buy&Hold: -12.5% ≈ -7.26R
- Strategy − B&H: -6.19R
- Yearly R: 2005:-1.3, 2006:-2.4, 2007:-1.5, 2008:+2.0, 2009:-0.2, 2010:-2.8, 2011:-0.0, 2012:-3.2, 2013:+0.2, 2014:-0.7, 2015:-2.7, 2016:+0.9, 2017:-1.4, 2018:-5.3, 2019:+9.5, 2020:-3.2, 2021:-3.8, 2022:-1.3, 2023:-1.5, 2024:+2.0, 2025:-0.1, 2026:+3.4

## Auto-screen (this run)
Candidates that cleared the bar:
- **AUDUSD BB fade +ADX 5y** (FX absolute edge: total +7.5R, edge vs B&H +8.9R)

Not financial advice.
