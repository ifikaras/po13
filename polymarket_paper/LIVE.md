# Polymarket Paper → Live Checklist

## Currently running: Musk tweet neg-risk only

LP rewards, weather edge, and wallet mirror paper bots are **stopped**.
Only the Musk Goldilocks + Runner-up NO sim keeps running.

```bash
# Musk-only paper loop (resumes saved positions)
python3 -m polymarket_paper.cli multi --only musk --interval 300

# Status
python3 -m polymarket_paper.cli status

# Logs
tail -f data/strategies_daily.log
```

---

## LP paper daemon (stopped — not live)

Target was **~$3–4/day conservative** (10% of model rewards − $3/day fill drag).
Do not start this unless you explicitly want LP again.

```bash
# Auto-size capital + pick a larger reward pool for ~$3.5/day
python3 -m polymarket_paper.cli size --target-daily 3.5

# Run all day (1 sample/min, stops at UTC midnight) — auto bankroll/order
python3 -m polymarket_paper.cli daemon --reset --target-daily 3.5

# Last LP snapshot (daemon is not running)
python3 -m polymarket_paper.cli lp-status
```

Conservative estimate uses: **10% of model reward share**, minus simulated fills, minus **$3/day** fill drag.
The picker ignores tiny pools (<~$40/day) and ranks markets by expected conservative net.

---

## Live trading — what YOU must do

### 1. Account & wallet
- Create account at [polymarket.com](https://polymarket.com)
- Connect wallet (MetaMask, Rabby, etc.) on **Polygon**
- Complete any KYC/restrictions for your region

### 2. Fund the wallet
- **USDC on Polygon** (not Ethereum mainnet)
- For ~$3–4/day conservative target: typically **~$225** virtual/live bankroll
  - ~$150 locked in two $75 orders on a larger reward pool (~$90+/day)
  - Rest as buffer for fills / repositioning
- Minimum tiny-pool experiments: **$100–150** (often < $1–2/day after haircuts)
- Optional: small amount of **MATIC/POL** for gas (usually minimal on Polymarket)

### 3. Deposit to Polymarket
- In Polymarket UI: Deposit USDC from wallet → Polymarket balance
- This is the balance used for limit orders

### 4. Choose a market
- Pick a market with **Liquidity Rewards** (reward icon in UI)
- Check: `rewards_min_size`, `max spread`, `daily pool`
- API: `https://clob.polymarket.com/rewards/markets/current`

### 5. Place initial orders MANUALLY
The open-source bot (`polymarket_lp_tool`) **does not create first orders**.
You must:
1. Open the market on Polymarket
2. Place **limit BUY** below mid (inside reward zone)
3. Place **limit SELL** above mid (or buy NO — same effect)
4. Meet **minimum size** (often $20)

### 6. API keys for the reposition bot (optional automation)
If using `lihanyu81/polymarket_lp_tool`:

```bash
git clone https://github.com/lihanyu81/polymarket_lp_tool
cd polymarket_lp_tool
cp .env.example .env
```

Fill in `.env`:
- `PK` — wallet private key (⚠️ never share; use dedicated wallet)
- CLOB API creds (derived via py-clob-client from PK)
- Optional: Telegram for alerts

The bot will **monitor and move** your existing orders — not deposit funds for you.

### 7. Run 24/7
- Use a **VPS** (AWS, Hetzner, etc.) — home PC works but less reliable
- Run under `systemd`, `tmux`, or Docker
- Monitor fills daily — adverse fills are the main risk

### 8. Risks you accept live
| Risk | What happens |
|------|----------------|
| **Fill** | Order executes → you hold YES/NO shares → can lose if price moves |
| **Adverse selection** | Informed traders hit your quote before news |
| **Competition** | More makers → smaller reward share |
| **Market resolution** | Binary outcome → one side goes to $0 |
| **Min payout** | Rewards under **$1/day** may not pay out |

### 9. Realistic live expectations ($100 capital)
| Scenario | Net/day |
|----------|---------|
| Conservative | **$2–5** |
| Base | **$5–15** |
| Optimistic (low competition) | **$15–30** |

Not guaranteed. Bad fills can wipe several days of rewards.

---

## Paper vs Live

| | Paper daemon | Live |
|--|-------------|------|
| Wallet | ❌ Not needed | ✅ Required |
| USDC | ❌ Virtual | ✅ Real deposit |
| Orders | ❌ Simulated | ✅ You place + bot moves |
| Rewards | 📊 Estimated | 💰 Real pUSD daily |
| Risk | None | Real loss possible |
