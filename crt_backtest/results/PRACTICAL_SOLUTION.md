# Practical solution screen

## Finding
Classic TA EAs (CRT, Donchian, RSI2, BB fade) either lag buy&hold on indices or fail out-of-sample on FX.

## What still makes sense as a BOT

### A) SMA200 crash filter (index)
Stay long only while Close > SMA200; otherwise cash. Goal: cut left-tail DD, not beat CAGR.
### B) Dual momentum (12m return > 0)
Similar risk filter with slightly different timing.
### C) Optional small FX sleeve
NZDUSD BB+ADX showed the only mildly persistent positive absolute R across MAX/10y/5y, but PF is thin (~1.1–1.2) — research sleeve, not a money printer.

## Overlay numbers

### US100 5y
- B&H: CAGR +13.6%, MaxDD -35.3%
- SMA200 filter: CAGR +13.2%, MaxDD -20.0% (in market ~73%)
- DualMom: CAGR +10.1%, MaxDD -26.8% (in market ~77%)

### US100 10y
- B&H: CAGR +19.9%, MaxDD -35.3%
- SMA200 filter: CAGR +17.5%, MaxDD -21.5% (in market ~73%)
- DualMom: CAGR +13.2%, MaxDD -37.5% (in market ~77%)

### US100 MAX
- B&H: CAGR +8.4%, MaxDD -79.0%
- SMA200 filter: CAGR +9.1%, MaxDD -32.7% (in market ~73%)
- DualMom: CAGR +9.4%, MaxDD -37.5% (in market ~77%)

### SPX 5y
- B&H: CAGR +11.3%, MaxDD -25.4%
- SMA200 filter: CAGR +8.4%, MaxDD -19.7% (in market ~67%)
- DualMom: CAGR +9.5%, MaxDD -21.9% (in market ~69%)

### SPX 10y
- B&H: CAGR +13.5%, MaxDD -33.9%
- SMA200 filter: CAGR +9.2%, MaxDD -19.7% (in market ~67%)
- DualMom: CAGR +10.3%, MaxDD -21.9% (in market ~69%)

### SPX MAX
- B&H: CAGR +6.4%, MaxDD -86.2%
- SMA200 filter: CAGR +6.8%, MaxDD -51.6% (in market ~67%)
- DualMom: CAGR +5.7%, MaxDD -44.5% (in market ~69%)

Not financial advice.