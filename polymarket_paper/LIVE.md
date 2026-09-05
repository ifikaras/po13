# Polymarket Paper → Live Checklist

## Currently running: Musk tweet neg-risk only

LP rewards, weather edge, and wallet mirror are **stopped**.
Only the Musk Goldilocks + Runner-up NO sim keeps running.

```bash
python3 -m polymarket_paper.cli multi --only musk --interval 300
python3 -m polymarket_paper.cli status
tail -f data/strategies_daily.log
```

---

## LP / other strategies (stopped)

To restart later:

```bash
python3 -m polymarket_paper.cli multi --only weather mirror musk --interval 300
python3 -m polymarket_paper.cli daemon --reset --bankroll 225 --order-size 75 --target-daily 3.5 --no-midnight-stop
```
