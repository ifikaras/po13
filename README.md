# po13

## Daily Value Bet (Novibet) — zero setup for you

**You do nothing technical.** No code, no config files.

### Your daily workflow

1. **Agent scans** all Novibet-likely matches and sends numbered list
2. You open Novibet and reply with odds: **`#5 BTTS Όχι 2.03`** or screenshot
3. Agent replies: **ΠΑΙΞΕ** or **SKIP** (+ stake suggestion)
4. Message **`καβά`** anytime for bankroll / open bets

You do **not** need to suggest matches — the agent initiates the scan.

### What the agent does automatically

- Scans upcoming football fixtures (major leagues on Novibet)
- Poisson model + FotMob stats
- Picks one bet with best model edge (no hard odds cap — edge tiers decide PLAY/SKIP)
- Evaluates value when you report Novibet odds

### Professional gates (market-anchored)

| Odds | Min *anchored* edge to PLAY |
|------|-----------------------------|
| 1.40 – 2.50 | +3% |
| 2.50 – 4.00 | +5% |
| 4.00+ | +8% |

**Market-anchor (bookmaker mode):** model probability is shrunk toward the soft/sharp market. Raw model edges above **+12%** without market confirm are rejected. Model vs market divergence > **12pp** defers to market. Absolute believable edge cap: **+15%**.

Preferred daily-pick band: **1.70–2.50** (stability), but higher odds are fine if *anchored* edge clears the tier.

### Pinnacle sharp lines

Official Pinnacle API is **closed to the public** (July 2025). We use **pinnapi** (Pinnacle feed mirror):

1. Free key: https://pinnapi.com (100 REST req/day)
2. Add Cursor secret: `PINNAPI_KEY`
3. Agent auto-anchors Novibet offers to Pinnacle moneyline / totals / derived DC

Without the key, soft-sanity market-anchor still runs (no sharp blend).

### Limitations

- **Novibet odds:** agent cannot read Novibet directly (bot block). You check the app once (~30 sec).
- **Football:** full statistical model. Other sports: ask agent for a pick when basketball/NBA is in season.

### Value formula

`(model_probability × odds - 1) × 100` after **market-anchor** — PLAY if anchored edge meets the tier for that odds (see table above)
