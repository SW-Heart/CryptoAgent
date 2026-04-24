import json
import threading
from typing import List, Any
from app.database import get_db

from .telegram import TelegramChannel
from .feishu import FeishuChannel
from .dingtalk import DingtalkChannel
from .wechat import WechatChannel

class NotifierEngine:
    def __init__(self):
        pass

    def send_event(self, user_id: str, event_type: str, title: str, body: str, level: str = "INFO"):
        """
        Sends an event to all configured and enabled channels for the user asynchronously.
        event_type options: "TRADE_OPEN", "TRADE_CLOSE", "SL_TRIGGERED", "SYSTEM_ALERT", "DAILY_REPORT"
        level options: "INFO", "WARN", "URGENT", "DAILY"
        """
        if not user_id:
            return
            
        def _send():
            channels = self._get_user_channels(user_id, event_type)
            for channel in channels:
                try:
                    channel.send(title, body, level)
                except Exception as e:
                    print(f"[Notifier Engine] Error sending to channel {type(channel)}: {e}")
                    
        # Fire and forget in a background thread
        threading.Thread(target=_send, daemon=True).start()
        
    def send_all(self, title: str, body: str, level: str = "INFO", event_type: str = "SYSTEM_ALERT"):
        """
        Sends an event to ALL users across ALL their configured channels.
        Used for urgent global alerts.
        """
        def _send():
            try:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT user_id, channel, config, enabled_events 
                            FROM notification_configs
                            WHERE is_active = TRUE
                        """)
                        rows = cur.fetchall()
                        
                        channels_to_send = []
                        for row in rows:
                            events = row["enabled_events"]
                            if isinstance(events, str):
                                try:
                                    events = json.loads(events)
                                except:
                                    events = []
                                    
                            if event_type in events:
                                ch_type = row["channel"]
                                config = row["config"]
                                if isinstance(config, str):
                                    try:
                                        config = json.loads(config)
                                    except:
                                        config = {}
                                
                                ch = self._create_channel(ch_type, config)
                                if ch:
                                    channels_to_send.append(ch)
                                    
                        for ch in channels_to_send:
                            try:
                                ch.send(title, body, level)
                            except:
                                pass
            except Exception as e:
                print(f"[Notifier Engine] Error in send_all: {e}")

        threading.Thread(target=_send, daemon=True).start()
        
    def _create_channel(self, ch_type: str, config: dict):
        if ch_type == "telegram":
            return TelegramChannel(config.get("bot_token"), config.get("chat_id"))
        elif ch_type == "feishu":
            return FeishuChannel(config.get("webhook_url"))
        elif ch_type == "dingtalk":
            return DingtalkChannel(config.get("webhook_url"), config.get("secret"))
        elif ch_type == "wechat":
            return WechatChannel(config.get("webhook_url"))
        return None
        
    def _get_user_channels(self, user_id: str, event_type: str) -> List[Any]:
        active_channels = []
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT channel, config, enabled_events 
                        FROM notification_configs
                        WHERE user_id = %s AND is_active = TRUE
                    """, (user_id,))
                    rows = cur.fetchall()
                    
                    for row in rows:
                        events = row["enabled_events"]
                        if isinstance(events, str):
                            try:
                                events = json.loads(events)
                            except:
                                events = []
                                
                        if event_type in events:
                            ch_type = row["channel"]
                            config = row["config"]
                            if isinstance(config, str):
                                try:
                                    config = json.loads(config)
                                except:
                                    config = {}
                                    
                            ch = self._create_channel(ch_type, config)
                            if ch:
                                active_channels.append(ch)
        except Exception as e:
            print(f"[Notifier Engine] Error fetching user channels: {e}")
            
        return active_channels

# Global singleton
notifier = NotifierEngine()
