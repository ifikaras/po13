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

    python -m futures_bot --once          # one live-market scan, still paper orders
    python -m futures_bot --loop --every 300

Edit `config/futures_bot.yaml` for score / R:R / risk / max positions.
"""
