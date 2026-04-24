"""
CryptoQuant Backend - Main Entry Point

FastAPI 应用入口。
Run with: fastapi dev main.py
"""
import json
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, Form
from fastapi.middleware.cors import CORSMiddleware

# Import middleware
from core.middleware import RateLimitMiddleware, UserContextMiddleware

# Import dynamic agent factory
from agents.trading_agent import get_trading_agent
from tools.trading_tools import set_current_user

# Import initialization functions
from app.routers.strategy import init_strategy_tables
from app.services.workspace_service import init_workspace_tables
from binance_client import init_binance_tables
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events: startup and shutdown"""
    print("[Main] Initializing database tables...")
    try:
        init_db()
        init_strategy_tables()
        init_binance_tables()
        init_workspace_tables()
        print("[Main] Tables initialized successfully")
        
        from scheduler import start_scheduler
        print("[Main] Auto-starting Strategy Scheduler...")
        start_scheduler()
    except Exception as e:
        print(f"[Main] Error initializing tables: {e}")
    
    yield
    print("[Main] Shutting down...")


# ============= Application Setup =============

app = FastAPI(lifespan=lifespan)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(UserContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============= Agent Routes =============

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
    
    agent = get_trading_agent(user_id, trader_instance_id=trader_instance_id)
    if not agent:
        return Response(content=json.dumps({"error": "Failed to initialize agent for user. Please check LLM configuration."}), status_code=400)
    
    try:
        instance_label = f" (trader #{trader_instance_id})" if trader_instance_id else ""
        print(f"[Main] Running dynamic agent for user {user_id[:8]}{instance_label}...")
        
        # 关键修复：在 endpoint context 中直接设置 user_id。
        # UserContextMiddleware 中的 set_current_user 设置的 ContextVar 无法可靠
        # 传播到 BaseHTTPMiddleware.call_next() 内部（Starlette 在独立的 task 中
        # 执行 endpoint）。必须在 endpoint 函数内部再次设置，确保 asyncio.to_thread
        # 复制 context 时能获取到正确的 user_id。
        set_current_user(user_id)
        if trader_instance_id:
            try:
                from tools.trading_tools import set_current_trader_id
                set_current_trader_id(int(trader_instance_id))
            except: pass
        
        # 使用 asyncio.to_thread 在线程池中运行同步的 agent.run()，
        # 避免阻塞事件循环，确保其他 HTTP 请求（前端轮询等）不被卡住
        run_response = await asyncio.to_thread(agent.run, input=message, session_id=session_id)
        
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
from app.routers.notifiers import router as notifiers_router
from app.routers.backtest_router import router as backtest_router
app.include_router(strategy_router)
app.include_router(workspace_router)
app.include_router(notifiers_router)
app.include_router(backtest_router)


print("[Main] CryptoAgent Backend Streamlined - Focus: Pure Strategy Trading with Multi-LLM Support")
