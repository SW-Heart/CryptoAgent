"""
Strategy Config Routes - 配置和管理路由
从 strategy.py 拆分而来：日志/调度器/策略配置/Beta/LLM/诊断
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import os
from datetime import datetime
from app.database import get_db_connection

router = APIRouter()

STRATEGY_ADMIN_USER_ID = "ee20fa53-5ac2-44bc-9237-41b308e291d8"

@router.get("/logs")
def get_strategy_logs(user_id: str = None, limit: int = 10, offset: int = 0, trader_instance_id: str = None):
    """Get strategy logs with pagination support, filtered by user_id"""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
        
    try:
        conn = get_db_connection()
        
        with conn.cursor() as cursor:
            # 降级：仅按 user_id，不论 trader_instance_id
            cursor.execute("SELECT COUNT(*) FROM strategy_logs WHERE user_id = %s OR user_id IS NULL", (user_id,))
            total_count = cursor.fetchone()[0]
            
            cursor.execute(
                "SELECT * FROM strategy_logs WHERE user_id = %s OR user_id IS NULL ORDER BY timestamp DESC LIMIT %s OFFSET %s",
                (user_id, limit, offset)
            )
            rows = cursor.fetchall()
        conn.close()
        
        logs = [dict(row) for row in rows]
        has_more = offset + len(logs) < total_count
        
        return {
            "logs": logs,
            "total": total_count,
            "has_more": has_more
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs-debug")
def debug_logs():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, user_id, trader_instance_id, symbols FROM strategy_logs ORDER BY timestamp DESC LIMIT 10")
            rows = cursor.fetchall()
            
            cursor.execute("SELECT id, user_id, status, is_enabled FROM trader_instances")
            instances = cursor.fetchall()
            
            return {
                "debug_logs": [dict(r) for r in rows],
                "instances": [dict(i) for i in instances]
            }
    except Exception as e:
        return {"error": str(e)}

@router.delete("/logs")
def clear_strategy_logs(user_id: str = None):
    """Clear strategy logs for the active trader instance"""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
        
    try:
        from app.routers.strategy import _get_active_client
        from app.services.workspace_service import list_trader_instances
        
        # 确定当前实盘实例
        instances = list_trader_instances(user_id)
        primary = next((i for i in instances if i["status"] == "RUNNING"), None)
        if not primary:
            primary = next((i for i in instances if i["is_enabled"]), None)
            
        instance_id = str(primary["id"]) if primary else None
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if instance_id:
                cursor.execute("DELETE FROM strategy_logs WHERE trader_instance_id = %s", (instance_id,))
            else:
                cursor.execute("DELETE FROM strategy_logs WHERE user_id = %s", (user_id,))
            conn.commit()
        conn.close()
        return {"success": True, "message": "Strategy logs cleared successfully for active instance"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/equity-curve")
def get_equity_curve():
    """Get equity curve data from closed positions"""
    try:
        conn = get_db_connection()
        
        # Get initial balance (use user_id for consistency)
        with conn.cursor() as cursor:
            cursor.execute("SELECT initial_balance FROM virtual_wallet WHERE user_id = %s", (STRATEGY_ADMIN_USER_ID,))
            wallet = cursor.fetchone()
            initial = wallet["initial_balance"] if wallet else 10000
            
            # Get all closed positions ordered by close time (filtered by user_id)
            cursor.execute("""
                SELECT closed_at, realized_pnl 
                FROM positions 
                WHERE status IN ('CLOSED', 'LIQUIDATED') AND closed_at IS NOT NULL AND user_id = %s
                ORDER BY closed_at ASC
            """, (STRATEGY_ADMIN_USER_ID,))
            rows = cursor.fetchall()
        conn.close()
        
        # Build equity curve
        curve = [{"time": None, "equity": initial}]
        running_equity = initial
        
        for row in rows:
            running_equity += row["realized_pnl"] or 0
            curve.append({
                "time": row["closed_at"],
                "equity": round(running_equity, 2)
            })
        
        return {"curve": curve}
    except Exception as e:
        print(f"[EquityCurve] Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trigger")
def trigger_strategy_manually():
    """Manually trigger a test trade (for testing)"""
    from datetime import datetime
    
    round_id = datetime.now().strftime("%Y-%m-%d_%H:%M")
    
    try:
        # Import trading tools directly (avoid proxy issues with requests)
        from tools.trading_tools import open_position, get_positions_summary
        
        # Get current positions
        summary = get_positions_summary()
        
        # Log to strategy_logs
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO strategy_logs (round_id, symbols, market_analysis, position_check, strategy_decision, actions_taken, raw_response)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                round_id, 
                "BTC,ETH,SOL", 
                f"Manual trigger test at {round_id}",
                f"Current positions: {summary['position_count']}, Balance: ${summary['wallet']['current_balance']}",
                "Test trigger completed",
                "[]",
                f"Manual test - Wallet: {summary['wallet']}"
            ))
            conn.commit()
        conn.close()
        
        return {
            "success": True,
            "round_id": round_id,
            "wallet": summary["wallet"],
            "positions": summary["open_positions"],
            "message": "Strategy log created. To test trading, use /api/strategy/test-trade"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-trade")
async def test_trade(symbol: str = "BTC", direction: str = "LONG", margin: float = 500):
    """Create a test trade position"""
    try:
        from tools.trading_tools import open_position
        
        result = open_position(
            symbol=symbol,
            direction=direction,
            margin=margin,
            stop_loss=None,
            take_profit=None
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============= Scheduler Control Endpoints =============

@router.get("/scheduler/status")
async def get_scheduler_status():
    """Get scheduler running status"""
    try:
        from scheduler import get_scheduler_status as get_status
        status = get_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduler/start")
async def start_scheduler(user_id: str = None):
    """Start the scheduler (admin only)"""
    # Verify admin permission
    if user_id != STRATEGY_ADMIN_USER_ID:
        raise HTTPException(
            status_code=403, 
            detail="Permission denied. Only admin can control the scheduler."
        )
    
    try:
        from scheduler import start_scheduler as start_sched
        result = start_sched()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduler/stop")
async def stop_scheduler(user_id: str = None):
    """Stop the scheduler (admin only)"""
    # Verify admin permission
    if user_id != STRATEGY_ADMIN_USER_ID:
        raise HTTPException(
            status_code=403, 
            detail="Permission denied. Only admin can control the scheduler."
        )
    
    try:
        from scheduler import stop_scheduler as stop_sched
        result = stop_sched()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============= Binance API Key Management =============

from pydantic import BaseModel

class BinanceKeysRequest(BaseModel):
    api_key: str
    api_secret: str
    is_testnet: bool = False  # Default to mainnet


@router.post("/binance/keys")
async def save_binance_keys(request: BinanceKeysRequest, user_id: str = None):
    """
    Save user's Binance API keys (encrypted).
    
    Args:
        request: API key and secret
        user_id: User ID (required)
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    
    try:
        from binance_client import save_user_api_keys, test_user_connection
        
        # First save the keys
        result = save_user_api_keys(
            user_id=user_id,
            api_key=request.api_key,
            api_secret=request.api_secret,
            is_testnet=request.is_testnet
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to save keys"))
        
        # Test the connection
        test_result = test_user_connection(user_id)
        
        return {
            "success": True,
            "message": "API keys saved successfully",
            "connection_test": test_result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/binance/keys")
async def delete_binance_keys(user_id: str = None):
    """
    Delete user's Binance API keys.
    
    Args:
        user_id: User ID (required)
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    
    try:
        from binance_client import delete_user_api_keys
        
        result = delete_user_api_keys(user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/binance/status")
async def get_binance_status(user_id: str = None):
    """
    Get Binance connection status for a user.
    
    Returns:
        - is_configured: Whether API keys are configured
        - is_trading_enabled: Whether trading is enabled
        - connection_ok: Whether connection test passed (if configured)
        - balance: USDT balance (if connected)
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    
    try:
        from binance_client import (
            has_user_api_keys,
            get_user_trading_status,
            test_user_connection
        )
        
        is_configured = has_user_api_keys(user_id)
        trading_status = get_user_trading_status(user_id)
        
        result = {
            "is_configured": is_configured,
            "is_trading_enabled": trading_status.get("is_trading_enabled", False),
            "enabled_at": trading_status.get("enabled_at"),
            "disabled_at": trading_status.get("disabled_at")
        }
        
        # If configured, test connection
        if is_configured:
            connection_test = test_user_connection(user_id)
            result["connection_ok"] = connection_test.get("success", False)
            if connection_test.get("success"):
                result["balance"] = connection_test.get("balance")
            else:
                result["connection_error"] = connection_test.get("error")
        else:
            result["connection_ok"] = False
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/binance/trading/enable")
async def enable_trading(user_id: str = None):
    """
    Enable trading for a user.
    Requires API keys to be configured first.
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    
    try:
        from binance_client import enable_user_trading, has_user_api_keys
        
        if not has_user_api_keys(user_id):
            raise HTTPException(
                status_code=400, 
                detail="Please configure Binance API keys first"
            )
        
        result = enable_user_trading(user_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/binance/trading/disable")
async def disable_trading(user_id: str = None):
    """
    Disable trading for a user.
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    
    try:
        from binance_client import disable_user_trading
        
        result = disable_user_trading(user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.delete("/reset")
async def reset_strategy(user_id: str = None):
    """
    Hard reset strategy tables (DROP & RECREATE).
    WARNING: This will delete all strategy data!
    """
    if user_id != STRATEGY_ADMIN_USER_ID:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            print("[Strategy] Resetting tables...")
            cursor.execute("DROP TABLE IF EXISTS strategy_logs")
            cursor.execute("DROP TABLE IF EXISTS orders")
            cursor.execute("DROP TABLE IF EXISTS positions")
            cursor.execute("DROP TABLE IF EXISTS virtual_wallet")
            conn.commit()
        conn.close()
        
        # Re-initialize
        init_strategy_tables()
        
        return {"success": True, "message": "Strategy tables reset successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ============= Manual Strategy Trigger =============

@router.post("/analysis/run")
def run_strategy_analysis(
    background_tasks: BackgroundTasks,
    symbols: str = "BTC,ETH,SOL",
    user_id: str = None
):
    """
    手动触发策略分析 (异步后台执行)。
    
    Args:
        symbols: 逗号分隔的币种列表
    """
    try:
        from scheduler import trigger_strategy
        
        # Add task to background queue (trigger_strategy reads profiles from DB)
        background_tasks.add_task(trigger_strategy)
        
        return {
            "status": "success",
            "message": f"Strategy analysis started for {symbols}",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============= Strategy Configuration =============

@router.get("/config")
def get_user_strategy_settings(user_id: str):
    """Get user-specific strategy configuration."""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    try:
        from binance_client import get_user_strategy_config
        return get_user_strategy_config(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/config/set")
def save_user_strategy_settings(user_id: str, config: dict):
    """Save user-specific strategy configuration."""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    try:
        from binance_client import save_user_strategy_config
        
        # Extract fields from config dict
        symbols = config.get("symbols")
        strategy_enabled = config.get("strategy_enabled")
        max_positions = config.get("max_positions")
        risk_per_trade = config.get("risk_per_trade")
        agent_requirements = config.get("agent_requirements")
        trading_interval = config.get("trading_interval")
        
        res = save_user_strategy_config(
            user_id=user_id,
            symbols=symbols,
            strategy_enabled=strategy_enabled,
            max_positions=max_positions,
            risk_per_trade=risk_per_trade,
            agent_requirements=agent_requirements,
            trading_interval=trading_interval
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============= Beta Access System =============
# 内测期间: 2026年4月 - 2026年5月

BETA_START_DATE = "2026-04-01"
BETA_END_DATE = "2026-05-31"

# 预设邀请码 (10个6位码)
BETA_INVITE_CODES = {
    "BETA26", "ALPHA8", "NEXUS1", "TRADE9", "SHARK7",
    "WHALE3", "MOON22", "DEGEN5", "HODL99", "PUMP88"
}



def init_beta_fields():
    """Add beta access fields to user_credits table if not exists."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Add beta_access column
            cursor.execute("""
                ALTER TABLE user_credits 
                ADD COLUMN IF NOT EXISTS beta_access BOOLEAN DEFAULT FALSE
            """)
            # Add beta_code_used column
            cursor.execute("""
                ALTER TABLE user_credits 
                ADD COLUMN IF NOT EXISTS beta_code_used TEXT
            """)
            # Add beta_activated_at column
            cursor.execute("""
                ALTER TABLE user_credits 
                ADD COLUMN IF NOT EXISTS beta_activated_at TIMESTAMP
            """)
            # Add username and avatar_url
            cursor.execute("""
                ALTER TABLE user_credits 
                ADD COLUMN IF NOT EXISTS username TEXT
            """)
            cursor.execute("""
                ALTER TABLE user_credits 
                ADD COLUMN IF NOT EXISTS avatar_url TEXT
            """)
            conn.commit()
            print("[Beta] Beta access fields initialized")
    except Exception as e:
        print(f"[Beta] Migration note: {e}")
    finally:
        conn.close()


# Run migration on module load
try:
    init_beta_fields()
except Exception as e:
    print(f"[Beta] Could not run migration: {e}")


@router.get("/beta/status")
def get_beta_status(user_id: str):
    """
    获取用户的内测资格状态。
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT beta_access, beta_code_used, beta_activated_at
                FROM user_credits
                WHERE user_id = %s
            """, (user_id,))
            row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {
                "has_beta_access": False,
                "beta_code_used": None,
                "beta_activated_at": None,
                "beta_period": {
                    "start": BETA_START_DATE,
                    "end": BETA_END_DATE
                }
            }
        
        return {
            "has_beta_access": row["beta_access"] or False,
            "beta_code_used": row["beta_code_used"],
            "beta_activated_at": row["beta_activated_at"].isoformat() if row["beta_activated_at"] else None,
            "beta_period": {
                "start": BETA_START_DATE,
                "end": BETA_END_DATE
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/beta/verify")
def verify_beta_code(user_id: str, code: str, username: str = None, avatar_url: str = None):
    """
    验证邀请码并激活内测资格。
    """
    if not user_id or not code:
        raise HTTPException(status_code=400, detail="user_id and code are required")
    
    # 转换为大写进行比对
    code_upper = code.strip().upper()
    
    if code_upper not in BETA_INVITE_CODES:
        return {
            "success": False,
            "error": "邀请码无效",
            "error_en": "Invalid invite code"
        }
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 检查用户是否存在，不存在则创建
            cursor.execute("SELECT user_id FROM user_credits WHERE user_id = %s", (user_id,))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO user_credits (user_id, credits, beta_access, beta_code_used, beta_activated_at, username, avatar_url)
                    VALUES (%s, 100, TRUE, %s, CURRENT_TIMESTAMP, %s, %s)
                """, (user_id, code_upper, username, avatar_url))
            else:
                # 更新现有用户
                cursor.execute("""
                    UPDATE user_credits 
                    SET beta_access = TRUE, 
                        beta_code_used = %s, 
                        beta_activated_at = CURRENT_TIMESTAMP,
                        username = COALESCE(%s, username),
                        avatar_url = COALESCE(%s, avatar_url)
                    WHERE user_id = %s
                """, (code_upper, username, avatar_url, user_id))
            conn.commit()
        conn.close()
        
        return {
            "success": True,
            "message": "内测资格已激活！",
            "message_en": "Beta access activated!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/beta/profile")
def update_beta_profile(user_id: str, username: str = None, avatar_url: str = None):
    """
    更新用户的头像和昵称（用于排行榜显示）。
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE user_credits 
                SET username = COALESCE(%s, username),
                    avatar_url = COALESCE(%s, avatar_url)
                WHERE user_id = %s
            """, (username, avatar_url, user_id))
            conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        print(f"[Beta] Update profile error: {e}")
        return {"success": False, "error": str(e)}


@router.get("/beta/leaderboard")
def get_beta_leaderboard(limit: int = 10):
    """
    获取内测用户胜率排行榜。
    
    从 binance_sync_state 表聚合数据，按胜率排序。
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 聚合每个用户的交易统计，同时获取 username 和 avatar_url
            cursor.execute("""
                SELECT 
                    bss.user_id,
                    SUM(bss.total_pnl) as total_pnl,
                    SUM(bss.total_trades) as total_trades,
                    SUM(bss.win_trades) as win_trades,
                    uc.beta_activated_at,
                    uc.username,
                    uc.avatar_url
                FROM binance_sync_state bss
                LEFT JOIN user_credits uc ON bss.user_id = uc.user_id
                WHERE uc.beta_access = TRUE
                GROUP BY bss.user_id, uc.beta_activated_at, uc.username, uc.avatar_url
                HAVING SUM(bss.total_trades) > 0
                ORDER BY (SUM(bss.win_trades)::float / NULLIF(SUM(bss.total_trades), 0)) DESC
                LIMIT %s
            """, (limit,))
            rows = cursor.fetchall()
            
            # 获取总参与人数
            cursor.execute("""
                SELECT COUNT(DISTINCT user_id) 
                FROM user_credits 
                WHERE beta_access = TRUE
            """)
            total_result = cursor.fetchone()
            total_participants = total_result[0] if total_result else 0
            
        conn.close()
        
        leaderboard = []
        for idx, row in enumerate(rows):
            total_trades = row["total_trades"] or 0
            win_trades = row["win_trades"] or 0
            win_rate = round(win_trades / total_trades * 100, 1) if total_trades > 0 else 0
            total_pnl = round(row["total_pnl"] or 0, 2)
            
            user_id = row["user_id"]

            # 优先使用真实昵称，否则使用脱敏 ID
            if row["username"]:
                display_name = row["username"]
            else:
                if len(user_id) > 8:
                    display_name = f"{user_id[:4]}...{user_id[-4:]}"
                else:
                    display_name = user_id[:4] + "..."
            
            leaderboard.append({
                "rank": idx + 1,
                "display_name": display_name,
                "avatar_url": row["avatar_url"],
                "win_rate": win_rate,
                "total_trades": total_trades,
                "total_pnl": total_pnl,
                "joined_at": row["beta_activated_at"].isoformat() if row["beta_activated_at"] else None
            })
        
        return {
            "leaderboard": leaderboard,
            "total_participants": total_participants,
            "beta_period": {
                "start": BETA_START_DATE,
                "end": BETA_END_DATE
            },
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"[Beta] Leaderboard error: {e}")
        return {
            "leaderboard": [],
            "total_participants": 0,
            "beta_period": {
                "start": BETA_START_DATE,
                "end": BETA_END_DATE
            },
            "last_updated": datetime.now().isoformat()
        }

# ============= LLM Configuration Endpoints =============

@router.get("/llm-config")
def get_llm_config(user_id: str):
    """获取用户的大模型配置（API Key 脱敏）"""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
        
    try:
        from binance_client import get_user_strategy_config
        config = get_user_strategy_config(user_id)
        
        has_key = False
        if config.get("llm_api_key_encrypted"):
            has_key = True
            
        return {
            "llm_provider": config.get("llm_provider", "deepseek"),
            "llm_model": config.get("llm_model", "deepseek-chat"),
            "has_api_key": has_key
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/llm-config")
def update_llm_config(
    user_id: str,
    llm_provider: str,
    llm_model: str,
    llm_api_key: str = None
):
    """更新用户的大模型配置，并在保存前进行连通性测试"""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
        
    try:
        from binance_client import encrypt_value, decrypt_value, get_user_strategy_config
        from agents.trading_agent import test_llm_connectivity
        import concurrent.futures
        
        # 1. Determine which API Key to use for testing
        test_api_key = None
        if llm_api_key and not llm_api_key.startswith("****"):
            test_api_key = llm_api_key
        else:
            # Try to get existing key for testing if changed model but kept same key
            config = get_user_strategy_config(user_id)
            if config.get("llm_api_key_encrypted"):
                test_api_key = decrypt_value(config["llm_api_key_encrypted"])
        
        if not test_api_key:
             raise HTTPException(status_code=400, detail="API Key is required for connectivity test")

        # 2. Perform Connectivity Test with 10s timeout
        print(f"[LLMConfig] Testing connectivity for {llm_provider}/{llm_model}...")
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(test_llm_connectivity, llm_provider, llm_model, test_api_key)
                success, error_msg = future.result(timeout=10)
                
                if not success:
                    raise HTTPException(status_code=400, detail=f"LLM Connectivity Test Failed: {error_msg}")
        except concurrent.futures.TimeoutError:
            raise HTTPException(status_code=408, detail="LLM Connectivity Test Timed Out (10s)")
        except Exception as e:
            if isinstance(e, HTTPException): raise e
            raise HTTPException(status_code=400, detail=f"Connectivity test error: {str(e)}")

        # 3. Encrypt API Key if provided
        encrypted_key = None
        if llm_api_key and not llm_api_key.startswith("****"):
            encrypted_key = encrypt_value(llm_api_key)
        
        # 4. Update DB
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if encrypted_key:
                cursor.execute("""
                    INSERT INTO user_strategy_config (user_id, llm_provider, llm_model, llm_api_key_encrypted)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        llm_provider = EXCLUDED.llm_provider,
                        llm_model = EXCLUDED.llm_model,
                        llm_api_key_encrypted = EXCLUDED.llm_api_key_encrypted,
                        updated_at = CURRENT_TIMESTAMP
                """, (user_id, llm_provider, llm_model, encrypted_key))
            else:
                cursor.execute("""
                    INSERT INTO user_strategy_config (user_id, llm_provider, llm_model)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        llm_provider = EXCLUDED.llm_provider,
                        llm_model = EXCLUDED.llm_model,
                        updated_at = CURRENT_TIMESTAMP
                """, (user_id, llm_provider, llm_model))
            conn.commit()
        conn.close()
        
        return {"success": True, "message": "LLM configuration updated"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Strategy] Error updating LLM config: {e}")
        raise HTTPException(status_code=500, detail="Failed to update LLM config")

@router.get("/ready-check")
def ready_check(user_id: str):
    """聚合校验用户是否已准备好开启自动交易"""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
        
    try:
        from binance_client import get_user_strategy_config
        
        # 结果容器
        checks = {
            "ready": True,
            "details": {
                "binance": {"ok": False, "message": "未配置交易所密钥", "tab": "exchange"},
                "llm": {"ok": False, "message": "未配置大模型密钥", "tab": "llm"},
                "strategy": {"ok": False, "message": "未配置策略参数", "tab": "strategy"}
            }
        }
        
        # 1. 检查 LLM 和部分策略配置
        config = get_user_strategy_config(user_id)
        if config:
            # LLM 检查
            if config.get("llm_api_key_encrypted"):
                checks["details"]["llm"]["ok"] = True
                checks["details"]["llm"]["message"] = f"已就绪 ({config.get('llm_model', 'Default')})"
            
            # 策略参数检查 (有默认值，如果为空则自动补全)
            symbols = config.get("symbols")
            if not symbols:
                symbols = "BTC,ETH,SOL" # 使用默认值补全
                
            checks["details"]["strategy"]["ok"] = True
            checks["details"]["strategy"]["message"] = f"已就绪 ({symbols})"
        
        # 2. 检查 Binance 密钥
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id FROM user_binance_keys WHERE user_id = %s", (user_id,))
            if cursor.fetchone():
                checks["details"]["binance"]["ok"] = True
                checks["details"]["binance"]["message"] = "已就绪"
        conn.close()
        
        # 计算总体 Ready 状态
        for key in checks["details"]:
            if not checks["details"][key]["ok"]:
                checks["ready"] = False
                break
                
        return checks
    except Exception as e:
        print(f"[ReadyCheck] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
