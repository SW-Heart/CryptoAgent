"""
OG Agent Backend - Main Entry Point

This is the FastAPI application entry point.
Run with: fastapi dev main.py
"""
import os
import json
import asyncio
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, Form
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# Import dynamic agent factory
from agents.trading_agent import get_trading_agent
from tools.trading_tools import set_current_user

# Import initialization functions
from app.routers.strategy import init_strategy_tables
from app.services.workspace_service import init_workspace_tables
from binance_client import init_binance_tables

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events: startup and shutdown"""
    # Startup: Initialize tables
    print("[Main] Initializing database tables...")
    try:
        init_strategy_tables()
        init_binance_tables()
        init_workspace_tables()
        print("[Main] Tables initialized successfully")
        
        # Auto-start strategy scheduler
        from scheduler import start_scheduler
        print("[Main] Auto-starting Strategy Scheduler...")
        start_scheduler()
    except Exception as e:
        print(f"[Main] Error initializing tables: {e}")
    
    yield
    print("[Main] Shutting down...")

app = FastAPI(lifespan=lifespan)

# ============= Rate Limiting Setup =============

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

app.add_middleware(RateLimitMiddleware)

# ============= User Context Middleware =============

class UserContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if "/runs" in str(request.url) or "/agent" in str(request.url):
            user_id = None
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
                            except: pass
                        elif "form" in content_type or "urlencoded" in content_type:
                            try:
                                from urllib.parse import parse_qs
                                form_data = parse_qs(body.decode("utf-8"))
                                user_id = form_data.get("user_id", [None])[0]
                            except: pass
                        request._body = body
                if user_id:
                    set_current_user(user_id)
            except Exception as e:
                print(f"[UserContext] Error: {e}")
        return await call_next(request)

app.add_middleware(UserContextMiddleware)

# ============= CORS =============

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============= Agent Routes (Manual Implementation) =============

@app.post("/agents/{agent_id}/runs")
async def run_agent(
    agent_id: str,
    message: str = Form(...),
    user_id: str = Form(...),
    session_id: str = Form(None),
    trader_instance_id: int = Form(None),
    stream: bool = Form(False)
):
    """
    Manual implementation of Agno Agent runs to support dynamic user-specific LLM settings.
    """
    if agent_id != "trading-strategy-agent":
        return Response(content=json.dumps({"error": "Agent not found"}), status_code=404)
    
    # 1. Get dynamic agent for this user (optionally scoped to a specific trader instance)
    agent = get_trading_agent(user_id, trader_instance_id=trader_instance_id)
    if not agent:
        return Response(content=json.dumps({"error": "Failed to initialize agent for user. Please check LLM configuration."}), status_code=400)
    
    # 2. Run the agent
    # Note: For now we only support non-streaming to simplify the migration
    try:
        instance_label = f" (trader #{trader_instance_id})" if trader_instance_id else ""
        print(f"[Main] Running dynamic agent for user {user_id[:8]}{instance_label}...")
        # 使用 asyncio.to_thread 在线程池中运行同步的 agent.run()，
        # 避免阻塞事件循环，确保其他 HTTP 请求（前端轮询等）不被卡住
        run_response = await asyncio.to_thread(agent.run, input=message, session_id=session_id)
        
        # 3. Format response to match Agno's standard (useful for frontend compatibility)
        return {
            "content": run_response.content,
            "session_id": run_response.session_id,
            "user_id": user_id,
            "metrics": run_response.metrics
        }
    except Exception as e:
        print(f"[Main] Agent run error: {e}")
        return Response(content=json.dumps({"error": str(e)}), status_code=500)

# ============= Standard Routers =============

from app.routers.strategy import router as strategy_router
from app.routers.workspace import router as workspace_router
app.include_router(strategy_router)
app.include_router(workspace_router)

print("[Main] CryptoAgent Backend Streamlined - Focus: Pure Strategy Trading with Multi-LLM Support")
