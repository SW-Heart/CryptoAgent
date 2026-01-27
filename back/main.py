"""
OG Agent Backend - Main Entry Point

This is the FastAPI application entry point.
Run with: fastapi dev main.py
"""
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import json
import threading

# Import both Agents
# Import agents
from agents.crypto_agent import crypto_agent
from agents.trading_agent import trading_agent
from agents.daily_report_agent import daily_report_agent
from agents.swap_agent import swap_agent  # A2UI DEX 交易 Agent
from agno.os import AgentOS

# Import user context setter
from tools.trading_tools import set_current_user

# Create AgentOS with all agents
agent_os = AgentOS(agents=[crypto_agent, trading_agent, daily_report_agent, swap_agent])
app = agent_os.get_app()

# Middleware to set user context for trading tools
class UserContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract user_id from request for agent runs
        if "/v1/runs" in str(request.url) or "/agent" in str(request.url):
            user_id = None
            try:
                # Try to get user_id from query params first
                user_id = request.query_params.get("user_id")
                print(f"[UserContext] Query param user_id: {user_id}")
                
                # If not in query, try to read from body (for POST requests)
                if not user_id and request.method == "POST":
                    body = await request.body()
                    if body:
                        content_type = request.headers.get("content-type", "")
                        print(f"[UserContext] Content-Type: {content_type}")
                        print(f"[UserContext] Body preview: {body[:200]}")
                        
                        # Handle JSON format
                        if "application/json" in content_type:
                            try:
                                data = json.loads(body)
                                user_id = data.get("user_id")
                            except:
                                pass
                        
                        # Handle form-data format (multipart or urlencoded)
                        elif "form" in content_type or "urlencoded" in content_type:
                            try:
                                # Parse as form data
                                from urllib.parse import parse_qs
                                form_data = parse_qs(body.decode("utf-8"))
                                user_id = form_data.get("user_id", [None])[0]
                                print(f"[UserContext] Parsed form user_id: {user_id}")
                            except Exception as pe:
                                print(f"[UserContext] Parse error: {pe}")
                        
                        # Reset body for downstream handlers
                        request._body = body
                
                if user_id:
                    set_current_user(user_id)
                    print(f"[UserContext] Set user: {user_id[:8]}...")
                else:
                    print(f"[UserContext] No user_id found in request")
            except Exception as e:
                print(f"[UserContext] Error: {e}")
        
        response = await call_next(request)
        return response

app.add_middleware(UserContextMiddleware)

# Token Credit Middleware - 扣除 agent token 消耗积分
from app.routers.credits import deduct_token_credits

class TokenCreditMiddleware(BaseHTTPMiddleware):
    """拦截 agent runs 响应，统计 token 并扣除积分
    
    规则：5万 token = 1积分，向上取整
    仅处理非流式响应（stream=false）
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # 只处理 agent runs 端点
        url_path = str(request.url.path)
        if "/agents/" in url_path and "/runs" in url_path and request.method == "POST":
            # 检查是否为非流式响应（JSON 类型）
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    # 读取响应体
                    body = b""
                    async for chunk in response.body_iterator:
                        body += chunk
                    
                    data = json.loads(body.decode())
                    
                    # 提取 metrics 和 user_id
                    metrics = data.get("metrics", {})
                    total_tokens = metrics.get("total_tokens", 0)
                    user_id = data.get("user_id")
                    session_id = data.get("session_id")
                    
                    if total_tokens > 0 and user_id:
                        # 扣除积分
                        result = deduct_token_credits(user_id, total_tokens, session_id)
                        print(f"[TokenCredit] User {user_id}: {total_tokens:,} tokens -> -{result['deducted']} credits")
                        
                        # 可选：注入积分扣除信息到响应
                        data["credits_deducted"] = result
                        body = json.dumps(data).encode()
                    
                    # 重新构建响应 - 不复制原始 Content-Length，让框架自动计算
                    new_headers = {k: v for k, v in response.headers.items() 
                                   if k.lower() != "content-length"}
                    return Response(
                        content=body,
                        status_code=response.status_code,
                        headers=new_headers,
                        media_type=response.media_type
                    )
                except Exception as e:
                    print(f"[TokenCreditMiddleware] Error processing response: {e}")
                    # 如果处理失败，返回原始响应体
                    new_headers = {k: v for k, v in response.headers.items() 
                                   if k.lower() != "content-length"}
                    return Response(
                        content=body if 'body' in locals() else b"",
                        status_code=response.status_code,
                        headers=new_headers,
                        media_type=response.media_type
                    )
        
        return response

app.add_middleware(TokenCreditMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
from app.routers.dashboard import router as dashboard_router
from app.routers.sessions import router as sessions_router
from app.routers.credits import router as credits_router
from app.routers.strategy import router as strategy_router
from app.routers.daily_report import router as daily_report_router

app.include_router(dashboard_router)
app.include_router(sessions_router)
app.include_router(credits_router)
app.include_router(strategy_router)
app.include_router(daily_report_router)

# Initialize database tables
from app.routers.sessions import init_session_titles_table
from app.routers.credits import init_credits_table
from app.routers.strategy import init_strategy_tables
from binance_client import init_binance_tables

init_session_titles_table()
init_credits_table()
init_strategy_tables()
init_binance_tables()


# ============= Scheduler Integration =============
# Strategy Scheduler: Controlled via API endpoints (not auto-started)
#   GET  /api/strategy/scheduler/status - Get status
#   POST /api/strategy/scheduler/start  - Start (admin only)
#   POST /api/strategy/scheduler/stop   - Stop (admin only)
print("[Main] Strategy scheduler available via API (not auto-started)")

# Daily Report Scheduler: Always runs automatically (independent from strategy)
def start_daily_report_scheduler():
    """Start the daily report scheduler in background thread"""
    import schedule
    import time
    import os
    
    # Wait for FastAPI server to fully start
    time.sleep(5)
    
    print("[DailyReportScheduler] Starting...")
    
    DAILY_REPORT_HOUR = os.getenv("DAILY_REPORT_HOUR", "08:00")
    DAILY_EMAIL_HOUR = os.getenv("DAILY_EMAIL_HOUR", "08:05")
    
    from scheduler import generate_daily_report, send_daily_report_emails
    
    schedule.every().day.at(DAILY_REPORT_HOUR).do(generate_daily_report)
    schedule.every().day.at(DAILY_EMAIL_HOUR).do(send_daily_report_emails)
    
    print(f"[DailyReportScheduler] Daily Report at {DAILY_REPORT_HOUR} / Emails at {DAILY_EMAIL_HOUR} (local time)")
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

daily_report_thread = threading.Thread(target=start_daily_report_scheduler, daemon=True)
daily_report_thread.start()
print("[Main] Daily report scheduler started (always runs)")

# ============= Cache Warmup =============
# Pre-populate dashboard cache on startup to eliminate first-load delay
# from app.services.cache_warmup import start_warmup_thread
# warmup_thread = start_warmup_thread()
print("[Main] Cache warmup disabled")


# ============= Swap Quote API =============
# 供前端 SwapCard 获取实时报价数据
from fastapi import Query
from tools.swap_tools import get_swap_quote

@app.get("/api/swap/quote")
async def get_quote(
    from_token: str = Query(..., description="源代币符号"),
    to_token: str = Query(..., description="目标代币符号"),
    amount: float = Query(..., description="源代币数量"),
    network: str = Query("ethereum", description="网络")
):
    """获取 DEX 交易报价"""
    quote = get_swap_quote(from_token, to_token, amount, network)
    return quote




