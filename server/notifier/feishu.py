import requests
from .base import NotificationChannel

class FeishuChannel(NotificationChannel):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, title: str, body: str, level: str) -> bool:
        if not self.webhook_url:
            return False
        
        color = {"INFO": "blue", "WARN": "orange", "URGENT": "red", "DAILY": "green"}.get(level, "blue")
        
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": color
                },
                "elements": [
                    {"tag": "markdown", "content": body}
                ]
            }
        }
        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=5)
            res_json = resp.json()
            if res_json.get("code") != 0:
                print(f"[Feishu] Failed to send: {res_json}")
            return resp.status_code == 200 and res_json.get("code") == 0
        except Exception as e:
            print(f"[Feishu] Send error: {e}")
            return False
