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
- Picks one bet in odds range **1.70–1.85** with best edge
- Evaluates value when you report Novibet odds

### Limitations

- **Novibet odds:** agent cannot read Novibet directly (bot block). You check the app once (~30 sec).
- **Football:** full statistical model. Other sports: ask agent for a pick when basketball/NBA is in season.

### Value formula

`(model_probability × odds - 1) × 100` — play if ≥ +3%
