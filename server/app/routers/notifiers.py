from fastapi import APIRouter, Depends, HTTPException, Body
from app.database import get_db
import json
from pydantic import BaseModel
from typing import Dict, List, Any

# We don't have a formal auth router from what we saw, but user_id is injected via middleware or we can just expect it as query/form?
# Wait, let's just make it simple using query param or header for now if not available
# Looking at strategy router, we can see how they get user_id. Let's just use user_id: str in endpoint and assume the wrapper gets it or pass directly.
# Actually, the middleware `UserContextMiddleware` usually puts `X-User-Id` header. Let's use Header.
from fastapi import Header

router = APIRouter()

class ConfigUpdate(BaseModel):
    channel: str
    config: Dict[str, Any]
    enabled_events: List[str]
    is_active: bool

@router.get("/api/notifier/configs")
def get_configs(x_user_id: str = Header(None, alias="X-User-Id")):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, channel, config, enabled_events, is_active FROM notification_configs WHERE user_id = %s", (x_user_id,))
            rows = cur.fetchall()
            
            res = []
            for r in rows:
                events = r["enabled_events"]
                conf = r["config"]
                if isinstance(events, str):
                    try: events = json.loads(events)
                    except: events = []
                if isinstance(conf, str):
                    try: conf = json.loads(conf)
                    except: conf = {}
                res.append({
                    "id": r["id"],
                    "channel": r["channel"],
                    "config": conf,
                    "enabled_events": events,
                    "is_active": r["is_active"]
                })
            return {"success": True, "configs": res}

@router.post("/api/notifier/configs")
def save_config(req: ConfigUpdate, x_user_id: str = Header(None, alias="X-User-Id")):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO notification_configs (user_id, channel, config, enabled_events, is_active)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id, channel) DO UPDATE 
                SET config = EXCLUDED.config,
                    enabled_events = EXCLUDED.enabled_events,
                    is_active = EXCLUDED.is_active,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
            """, (x_user_id, req.channel, json.dumps(req.config), json.dumps(req.enabled_events), req.is_active))
            conn.commit()
            return {"success": True}

@router.post("/api/notifier/test")
def test_config(req: ConfigUpdate, x_user_id: str = Header(None, alias="X-User-Id")):
    from notifier.engine import notifier
    ch = notifier._create_channel(req.channel, req.config)
    if not ch:
        raise HTTPException(status_code=400, detail="Invalid channel type")
        
    ok = ch.send("✨ CryptoAgent 连通性测试", "这是一条测试消息，您的配置已成功生效！", "INFO")
    if not ok:
        raise HTTPException(status_code=400, detail="推送失败，请检查您的配置信息是否正确。")
    return {"success": True}
