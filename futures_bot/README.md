"""Paper-trading loop on top of the Crypto Futures Signal Scanner.

This package does **not** place live orders. It calls the existing scanner,
applies deterministic approval rules, and writes what it *would* have opened
into `data/futures_paper.json`.

Telegram is optional and has nothing to do with trading. It is only a
notification channel (a message on your phone when a paper order is recorded).
Leave it off unless you set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.

Quick start
-----------

    python -m futures_bot --once --self-test

That hits the scanner's offline demo (`DEMOUP`) so you can see an approval
without waiting on a full live scan.

Virtual / paper run against live markets (still no real orders):

    python -m futures_bot --once --reset-ledger --skip-confirmation
    python -m futures_bot --status
    python -m futures_bot --loop --every 300 --skip-confirmation

`--skip-confirmation` is TA-only (faster). Drop it later if you want OI / social
confirmation in the loop. `--reset-ledger` clears old paper trades first.

    python -m futures_bot --once          # one live-market scan, still paper orders
    python -m futures_bot --loop --every 300

Edit `config/futures_bot.yaml` for score / R:R / risk / max positions.
"""
