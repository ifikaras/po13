# po13

## Daily Value Bet (Novibet) — zero setup for you

**You do nothing technical.** No code, no config files.

### Your daily workflow

1. Message here: **«σημερινό pick»** or **«τι παίζω;»**
2. Agent replies: sport, match, market, fair odds, where to find it on Novibet
3. You check Novibet and reply with the odds (e.g. `1.84`)
4. Agent replies: **ΠΑΙΞΕ** or **SKIP** (value formula)

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

### Limitations

- **Novibet odds:** agent cannot read Novibet directly (bot block). You check the app once (~30 sec).
- **Football:** full statistical model. Other sports: ask agent for a pick when basketball/NBA is in season.

### Value formula

`(model_probability × odds - 1) × 100` after **market-anchor** — PLAY if anchored edge meets the tier for that odds (see table above)
