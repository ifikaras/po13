"""Optional notifications. Telegram is a messenger, not the exchange."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from futures_bot.config import NotifySettings


class Notifier:
    def __init__(self, settings: NotifySettings) -> None:
        self.settings = settings

    def send(self, text: str) -> None:
        print(text)
        if not self.settings.telegram_enabled:
            return
        token = self.settings.telegram_bot_token.strip()
        chat_id = self.settings.telegram_chat_id.strip()
        if not token or not chat_id:
            print("telegram enabled but TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing — skipped")
            return
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = urllib.parse.urlencode(
            {"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": "true"}
        ).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            if not body.get("ok"):
                print(f"telegram send failed: {body}")
        except urllib.error.URLError as exc:
            print(f"telegram send failed: {exc}")
