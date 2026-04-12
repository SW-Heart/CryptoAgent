"""
Core Middleware - Rate Limiting & User Context

提供 FastAPI 中间件：
- RateLimitMiddleware: 基于 IP/用户的速率限制
- UserContextMiddleware: 从请求中提取用户上下文
"""
import json
import time
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


# ============= Rate Limiting =============

def get_remote_address(request: Request) -> str:
    """获取客户端 IP 地址"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    client = request.client
    if client:
        return client.host
    return "unknown"


class SimpleRateLimiter:
    def __init__(self):
        self.requests = defaultdict(list)
        self.limits = {
            "agent": (10, 60),
            "binance": (30, 60),
            "default": (100, 60)
        }
    
    def _get_category(self, path: str) -> str:
        if "/agents/" in path or "/runs" in path:
            return "agent"
        elif "/api/strategy/binance" in path or "/trade" in path or "/order" in path:
            return "binance"
        return "default"
    
    def is_allowed(self, key: str, path: str) -> tuple[bool, str]:
        category = self._get_category(path)
        limit, window = self.limits[category]
        now = time.time()
        cache_key = f"{key}:{category}"
        self.requests[cache_key] = [t for t in self.requests[cache_key] if now - t < window]
        if len(self.requests[cache_key]) >= limit:
            remaining = int(window - (now - self.requests[cache_key][0]))
            return False, f"Rate limit exceeded ({category}: {limit}/min). Retry after {remaining}s"
        self.requests[cache_key].append(now)
        return True, ""


rate_limiter = SimpleRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = str(request.url.path)
        if path.startswith("/static") or path == "/health" or path == "/":
            return await call_next(request)
        user_id = request.query_params.get("user_id")
        key = user_id[:8] if user_id else get_remote_address(request)
        allowed, message = rate_limiter.is_allowed(key, path)
        if not allowed:
            return Response(
                content=json.dumps({"error": message, "code": "RATE_LIMITED"}),
                status_code=429,
                media_type="application/json"
            )
        return await call_next(request)


# ============= User Context =============

class UserContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if "/runs" in str(request.url) or "/agent" in str(request.url):
            user_id = None
            trader_instance_id = None
            try:
                user_id = request.query_params.get("user_id")
                if not user_id and request.method == "POST":
                    body = await request.body()
                    if body:
                        content_type = request.headers.get("content-type", "")
                        if "application/json" in content_type:
                            try:
                                data = json.loads(body)
                                user_id = data.get("user_id")
                                trader_instance_id = data.get("trader_instance_id")
                            except: pass
                        elif "form" in content_type or "urlencoded" in content_type:
                            try:
                                from urllib.parse import parse_qs
                                form_data = parse_qs(body.decode("utf-8"))
                                user_id = form_data.get("user_id", [None])[0]
                                trader_instance_id = form_data.get("trader_instance_id", [None])[0]
                            except: pass
                        request._body = body
                if user_id:
                    from tools.trading_tools import set_current_user
                    set_current_user(user_id)
                if trader_instance_id:
                    try:
                        from tools.trading_tools import set_current_trader_id
                        set_current_trader_id(int(trader_instance_id))
                    except: pass
            except Exception as e:
                print(f"[UserContext] Error: {e}")
        return await call_next(request)
