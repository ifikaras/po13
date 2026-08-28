# po13

## Value Bet Scanner (Novibet-first)

Σαρώνει **μόνο ό,τι παίζεις στη Novibet** — δεν έχει σημασία πρωτάθλημα ή άθλημα.

### Ροή καθημερινά

1. Άνοιξε **novibet.gr** και διάλεξε στοίχημα (ποδόσφαιρο, μπάσκετ, τένις, ό,τι έχεις)
2. Πρόσθεσέ το στο `config/novibet.yaml` με τις αποδόσεις Novibet
3. Τρέξε:

```bash
pip install -r requirements.txt
python -m value_scanner.cli
```

### Παράδειγμα `config/novibet.yaml`

```yaml
matches:
  - home: "Liverpool"
    away: "Nottingham Forest"
    sport: football
    odds:
      btts_no: 1.84

  - home: "Lakers"
    away: "Celtics"
    sport: basketball
    odds:
      home_win: 1.75
    model_probability:
      home_win: 0.58   # δική σου εκτίμηση για non-football
```

### Αυτόματες αποδόσεις Novibet (προαιρετικό)

```bash
export ODDS_API_IO_KEY=your_key   # odds-api.io — δωρεάν tier
python -m value_scanner.cli
```

### Εντολές

```bash
python -m value_scanner.cli --list-novibet    # τι έχει φορτωθεί
python -m value_scanner.cli --json            # JSON output
python -m value_scanner.cli --date 2026-08-29
```

### Value formula

`(model_probability × odds - 1) × 100`

- **Ποδόσφαιρο:** στατιστικά από FotMob + Poisson μοντέλο
- **Άλλα αθλήματα:** βάζεις `model_probability` χειροκίνητα
