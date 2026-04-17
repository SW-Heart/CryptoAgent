import requests
from .base import NotificationChannel

class TelegramChannel(NotificationChannel):
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def send(self, title: str, body: str, level: str) -> bool:
        if not self.bot_token or not self.chat_id:
            return False
            
        icon = {"INFO": "ℹ️", "WARN": "⚠️", "URGENT": "🚨", "DAILY": "📊"}.get(level, "ℹ️")
        text = f"{icon} *{title}*\n\n{body}"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        try:
            resp = requests.post(self.api_url, json=payload, timeout=5)
            if resp.status_code != 200:
                print(f"[Telegram] Failed to send: {resp.text}")
            return resp.status_code == 200
        except Exception as e:
            print(f"[Telegram] Send error: {e}")
            return False
