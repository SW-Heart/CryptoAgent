import requests
from .base import NotificationChannel

class WechatChannel(NotificationChannel):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, title: str, body: str, level: str) -> bool:
        if not self.webhook_url:
            return False
            
        color = {"INFO": "info", "WARN": "warning", "URGENT": "warning", "DAILY": "info"}.get(level, "comment")
        
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"**<font color=\"{color}\">{title}</font>**\n\n{body}"
            }
        }
        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=5)
            res_json = resp.json()
            if res_json.get("errcode", 0) != 0:
                print(f"[Wechat] Failed to send: {res_json}")
            return resp.status_code == 200 and res_json.get("errcode", 0) == 0
        except Exception as e:
            print(f"[Wechat] Send error: {e}")
            return False
