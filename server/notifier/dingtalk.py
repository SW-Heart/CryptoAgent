import requests
import time
import hmac
import hashlib
import base64
import urllib.parse
from .base import NotificationChannel

class DingtalkChannel(NotificationChannel):
    def __init__(self, webhook_url: str, secret: str = None):
        self.webhook_url = webhook_url
        self.secret = secret

    def send(self, title: str, body: str, level: str) -> bool:
        if not self.webhook_url:
            return False
            
        url = self.webhook_url
        if self.secret:
            timestamp = str(round(time.time() * 1000))
            string_to_sign = '{}\n{}'.format(timestamp, self.secret)
            string_to_sign_enc = string_to_sign.encode('utf-8')
            hmac_code = hmac.new(self.secret.encode('utf-8'), string_to_sign_enc, digestmod=hashlib.sha256).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
            if "?" in url:
                url = f"{url}&timestamp={timestamp}&sign={sign}"
            else:
                url = f"{url}?timestamp={timestamp}&sign={sign}"
            
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"### {title}\n\n{body}"
            }
        }
        try:
            resp = requests.post(url, json=payload, timeout=5)
            res_json = resp.json()
            if res_json.get("errcode", 0) != 0:
                print(f"[Dingtalk] Failed to send: {res_json}")
            return resp.status_code == 200 and res_json.get("errcode", 0) == 0
        except Exception as e:
            print(f"[Dingtalk] Send error: {e}")
            return False
