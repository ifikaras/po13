# po13

## Value Bet Scanner

Daily scanner that pulls team form from FotMob, estimates goal probabilities with a Poisson model, and flags value bets when bookmaker odds are available.

### Setup

```bash
pip install -r requirements.txt
```

Optional: set `THE_ODDS_API_KEY` for automatic odds (free tier at the-odds-api.com), or add manual odds in `config/odds.yaml`.

### Run

```bash
python -m value_scanner.cli --date 2026-08-29
python -m value_scanner.cli --json
```

### Manual odds example (`config/odds.yaml`)

```yaml
matches:
  "Liverpool vs Nottingham Forest":
    over_25: 1.78
    btts_yes: 1.72
```

Value formula: `(model_probability × odds - 1) × 100`
