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

# Import Agent and AgentOS from crypto_agent
from crypto_agent import crypto_agent, agent_os

# Import user context setter
from trading_tools import set_current_user

# Get the app from AgentOS
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
def start_scheduler_background():
    """Start the scheduler in a background thread"""
    import time
    
    # Wait for FastAPI server to fully start before scheduler makes API calls
    time.sleep(5)
    
    try:
        from scheduler import main as scheduler_main
        print("[Main] Starting scheduler in background thread...")
        scheduler_main()
    except Exception as e:
        print(f"[Main] Scheduler error: {e}")

# Start scheduler as daemon thread (won't block server shutdown)
scheduler_thread = threading.Thread(target=start_scheduler_background, daemon=True)
scheduler_thread.start()
print("[Main] Scheduler thread started (will begin after 5 seconds)")

