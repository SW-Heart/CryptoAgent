"""
OG Agent Backend - Main Entry Point

This is the FastAPI application entry point.
Run with: fastapi dev main.py
"""
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import json
import threading

# Import both Agents
# Import agents
from crypto_agent import crypto_agent
from trading_agent import trading_agent
from daily_report_agent import daily_report_agent
from agno.os import AgentOS

# Import user context setter
from trading_tools import set_current_user

# Create AgentOS with all agents
agent_os = AgentOS(agents=[crypto_agent, trading_agent, daily_report_agent])
app = agent_os.get_app()

# Middleware to set user context for trading tools
class UserContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract user_id from request for agent runs
        if "/v1/runs" in str(request.url) or "/agent" in str(request.url):
            try:
                # Try to get user_id from query params first
                user_id = request.query_params.get("user_id")
                
                # If not in query, try to read from body (for POST requests)
                if not user_id and request.method == "POST":
                    body = await request.body()
                    if body:
                        try:
                            data = json.loads(body)
                            user_id = data.get("user_id")
                        except:
                            pass
                        # Reset body for downstream handlers
                        request._body = body
                
                if user_id:
                    set_current_user(user_id)
            except:
                pass
        
        response = await call_next(request)
        return response

app.add_middleware(UserContextMiddleware)

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

init_session_titles_table()
init_credits_table()
init_strategy_tables()


# ============= Scheduler Integration =============
# Scheduler is now controlled via API endpoints:
#   GET  /api/strategy/scheduler/status - Get status
#   POST /api/strategy/scheduler/start  - Start (admin only)
#   POST /api/strategy/scheduler/stop   - Stop (admin only)
# Scheduler does NOT auto-start. Users control it via Strategy Nexus UI.
print("[Main] Scheduler available via API (not auto-started)")


