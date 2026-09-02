# Polymarket Paper → Live Checklist

## Paper daemon (virtual, no wallet)

```bash
# Run all day (1 sample/min, stops at UTC midnight)
python3 -m polymarket_paper.cli daemon --bankroll 100 --order-size 20

# Check progress anytime
python3 -m polymarket_paper.cli status

# Logs
tail -f data/polymarket_paper_daily.log
```

Conservative estimate uses: **10% of reward pool share**, minus simulated fills, minus **$3/day** fill drag.

---

## Live trading — what YOU must do

### 1. Account & wallet
- Create account at [polymarket.com](https://polymarket.com)
- Connect wallet (MetaMask, Rabby, etc.) on **Polygon**
- Complete any KYC/restrictions for your region

### 2. Fund the wallet
- **USDC on Polygon** (not Ethereum mainnet)
- Minimum practical: **$100–150**
  - $40 locked in two $20 orders (one market)
  - Rest as buffer for fills / repositioning
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
