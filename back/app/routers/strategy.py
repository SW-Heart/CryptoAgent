"""
Strategy API router.
Handles virtual trading, positions, and strategy logs.
"""
from fastapi import APIRouter, HTTPException
import os
from datetime import datetime
from app.database import get_db_connection as get_db_connection

router = APIRouter(prefix="/api/strategy", tags=["strategy"])

# DB_PATH removed

# Admin user ID for strategy operations (must match trading_tools.py)
STRATEGY_ADMIN_USER_ID = "ee20fa53-5ac2-44bc-9237-41b308e291d8"

# Binance API base URL (configurable via environment variable)
BINANCE_API_BASE = os.getenv("BINANCE_API_BASE", "https://api.binance.com")
from app.services.price_service import fetch_prices_batch

# def get_db_connection(): ... removed/imported

def init_strategy_tables():
    """Initialize strategy tables"""
    conn = get_db_connection()
    # Use cursor as context manager or just cursor()
    with conn.cursor() as cursor:
        # Virtual wallet
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS virtual_wallet (
                id SERIAL PRIMARY KEY,
                initial_balance DOUBLE PRECISION DEFAULT 10000,
                current_balance DOUBLE PRECISION DEFAULT 10000,
                total_pnl DOUBLE PRECISION DEFAULT 0,
                total_trades INTEGER DEFAULT 0,
                win_trades INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Positions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id SERIAL PRIMARY KEY,
                symbol TEXT NOT NULL,

            direction TEXT NOT NULL,
            leverage INTEGER DEFAULT 10,
            margin REAL NOT NULL,
            notional_value REAL NOT NULL,
            entry_price REAL NOT NULL,
            quantity REAL NOT NULL,
            stop_loss REAL,
            take_profit REAL,
            current_price REAL,
            unrealized_pnl REAL DEFAULT 0,
            status TEXT DEFAULT 'OPEN',
            opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP,
            close_price REAL,
            realized_pnl REAL
        )
    """)
    
    with conn.cursor() as cursor:
        # Orders history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                position_id INTEGER,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                direction TEXT,
                quantity DOUBLE PRECISION,
                margin DOUBLE PRECISION,
                entry_price DOUBLE PRECISION,
                stop_loss DOUBLE PRECISION,
                take_profit DOUBLE PRECISION,
                realized_pnl DOUBLE PRECISION,
                tp_level INTEGER,
                close_reason TEXT,
                fee DOUBLE PRECISION DEFAULT 0,
                status TEXT DEFAULT 'FILLED',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Strategy logs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategy_logs (
                id SERIAL PRIMARY KEY,
                round_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                symbols TEXT,
                market_analysis TEXT,
                position_check TEXT,
                strategy_decision TEXT,
                actions_taken TEXT,
                raw_response TEXT
            )
        """)
        conn.commit()
    
    # Initialize wallet if not exists
    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO virtual_wallet (id, initial_balance, current_balance)
            VALUES (1, 10000, 10000)
            ON CONFLICT (id) DO NOTHING
        """)
        conn.commit()
    conn.close()

# GET endpoints for UI

@router.get("/wallet")
def get_wallet(user_id: str = None):
    """Get wallet status with real-time equity.
    
    If user has Binance trading enabled, returns real Binance data.
    Otherwise returns virtual trading data (demo mode).
    """
    import requests
    
    # 如果用户启用了 Binance 交易，使用 Binance 数据
    if user_id:
        try:
            from tools.binance_trading_tools import binance_get_positions_summary
            from binance_client import get_user_trading_status
            
            status = get_user_trading_status(user_id)
            if status.get("is_configured") and status.get("is_trading_enabled"):
                result = binance_get_positions_summary(user_id)
                if "error" not in result:
                    return {
                        "source": "binance",
                        "initial_balance": None,  # Binance 不跟踪初始余额
                        "current_balance": result.get("available_balance", 0),
                        "margin_in_use": result.get("margin_in_use", 0),
                        "unrealized_pnl": result.get("unrealized_pnl", 0),
                        "equity": result.get("equity", 0),
                        "total_pnl": None,  # 需要单独跟踪
                        "total_trades": None,
                        "win_trades": None,
                        "win_rate": None,
                        "balance_breakdown": result.get("balance_breakdown", [])
                    }
        except Exception as e:
            print(f"[Strategy] Binance wallet error: {e}")
    
    # 虚拟交易模式（Demo）
    try:
        conn = get_db_connection()
        # Use user_id to match trading_tools.py logic
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM virtual_wallet WHERE user_id = %s", (STRATEGY_ADMIN_USER_ID,))
            row = cursor.fetchone()
            
            # Get open positions for equity calculation (filtered by user_id)
            cursor.execute("SELECT * FROM positions WHERE status = 'OPEN' AND user_id = %s", (STRATEGY_ADMIN_USER_ID,))
            positions = cursor.fetchall()
        conn.close()
        
        if not row:
            return {"error": "Wallet not initialized"}
        
        # Calculate real-time unrealized PnL
        total_unrealized_pnl = 0
        total_margin_in_use = 0
        
        # Batch fetch prices for all positions
        symbols = [f"{pos['symbol']}USDT" for pos in positions]
        price_map = fetch_prices_batch(symbols, BINANCE_API_BASE)

        for pos in positions:
            total_margin_in_use += pos["margin"]
            # 计算剩余数量（原始数量 - 已平仓数量）
            closed_qty = pos["closed_quantity"] if pos["closed_quantity"] else 0
            remaining_qty = pos["quantity"] - closed_qty
            
            symbol_pair = f"{pos['symbol']}USDT"
            current_price = price_map.get(symbol_pair)
            
            if current_price:
                # 使用剩余数量计算未实现盈亏
                if pos["direction"] == "LONG":
                    total_unrealized_pnl += remaining_qty * (current_price - pos["entry_price"])
                else:
                    total_unrealized_pnl += remaining_qty * (pos["entry_price"] - current_price)
            else:
                 # Fallback to stored PnL if real-time price unavailable
                total_unrealized_pnl += pos["unrealized_pnl"] or 0
        
        # Equity = current_balance + margin_in_use + unrealized_pnl
        equity = row["current_balance"] + total_margin_in_use + total_unrealized_pnl
        
        return {
            "source": "virtual",
            "initial_balance": row["initial_balance"],
            "current_balance": row["current_balance"],
            "margin_in_use": round(total_margin_in_use, 2),
            "unrealized_pnl": round(total_unrealized_pnl, 2),
            "equity": round(equity, 2),
            "total_pnl": row["total_pnl"],
            "total_trades": row["total_trades"],
            "win_trades": row["win_trades"],
            "win_rate": round(row["win_trades"] / row["total_trades"] * 100, 1) if row["total_trades"] > 0 else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
def get_positions(status: str = "OPEN", user_id: str = None):
    """Get positions (OPEN / CLOSED / ALL) with real-time PnL.
    
    If user has Binance trading enabled, returns real Binance positions.
    Otherwise returns virtual trading positions (demo mode).
    """
    import requests
    
    # 如果用户启用了 Binance 交易，使用 Binance 数据
    if user_id:
        try:
            from tools.binance_trading_tools import binance_get_positions_summary
            from binance_client import get_user_trading_status
            
            trading_status = get_user_trading_status(user_id)
            if trading_status.get("is_configured") and trading_status.get("is_trading_enabled"):
                result = binance_get_positions_summary(user_id)
                if "error" not in result:
                    # 转换为统一格式
                    positions = []
                    for pos in result.get("open_positions", []):
                        positions.append({
                            "id": None,  # Binance 没有我们的 position ID
                            "symbol": pos.get("symbol", "").replace("USDT", ""),
                            "direction": pos.get("direction"),
                            "leverage": pos.get("leverage", 10),
                            "margin": pos.get("margin", 0),
                            "notional_value": pos.get("quantity", 0) * pos.get("entry_price", 0),
                            "entry_price": pos.get("entry_price", 0),
                            "quantity": pos.get("quantity", 0),
                            "closed_quantity": 0,
                            "remaining_quantity": pos.get("quantity", 0),
                            "stop_loss": None,
                            "take_profit": None,
                            "current_price": pos.get("current_price", 0),
                            "unrealized_pnl": pos.get("unrealized_pnl", 0),
                            "realized_pnl": None,
                            "status": "OPEN",
                            "opened_at": None,
                            "closed_at": None,
                            "close_price": None,
                            "liquidation_price": pos.get("liquidation_price", 0),
                            "roi_percent": pos.get("roi_percent", 0)
                        })
                    return {"source": "binance", "positions": positions}
        except Exception as e:
            print(f"[Strategy] Binance positions error: {e}")
    
    # 虚拟交易模式（Demo）
    try:
        conn = get_db_connection()
        
        # Filter by user_id to only show admin's positions
        with conn.cursor() as cursor:
            if status == "ALL":
                cursor.execute("SELECT * FROM positions WHERE user_id = %s ORDER BY opened_at DESC", (STRATEGY_ADMIN_USER_ID,))
            else:
                cursor.execute(
                    "SELECT * FROM positions WHERE status = %s AND user_id = %s ORDER BY opened_at DESC",
                    (status, STRATEGY_ADMIN_USER_ID)
                )
            rows = cursor.fetchall()
        
        conn.close()
        
        positions = []
        for row in rows:
            # Fetch prices outside loop or just batch now? 
            # Ideally fetch all relevant symbols first.
            # But here we are iterating. Let's do a batch fetch before loop.
            pass # Placeholder to be removed by logic below
        
        # Batch fetch prices
        symbols = [f"{row['symbol']}USDT" for row in rows if row["status"] == "OPEN"]
        price_map = fetch_prices_batch(symbols, BINANCE_API_BASE)

        positions = []
        for row in rows:
            # Safely get leverage and notional_value (may not exist in old records)
            leverage = row["leverage"] if "leverage" in row.keys() else 10
            notional_value = row["notional_value"] if "notional_value" in row.keys() else row["margin"] * leverage
            
            # 计算阶段性平仓相关数据
            closed_qty = row["closed_quantity"] if "closed_quantity" in row.keys() and row["closed_quantity"] else 0
            remaining_qty = row["quantity"] - closed_qty
            
            pos_data = {
                "id": row["id"],
                "symbol": row["symbol"],
                "direction": row["direction"],
                "leverage": leverage,
                "margin": row["margin"],
                "notional_value": notional_value,
                "entry_price": row["entry_price"],
                "quantity": row["quantity"],
                "closed_quantity": closed_qty,
                "remaining_quantity": remaining_qty,
                "stop_loss": row["stop_loss"],
                "take_profit": row["take_profit"],
                "current_price": row["current_price"],
                "unrealized_pnl": row["unrealized_pnl"],
                "realized_pnl": row["realized_pnl"],
                "status": row["status"],
                "opened_at": row["opened_at"],
                "closed_at": row["closed_at"],
                "close_price": row["close_price"]
            }
            
            # For OPEN positions, get real-time price and calculate PnL
            if row["status"] == "OPEN":
                symbol_pair = f"{row['symbol']}USDT"
                current_price = price_map.get(symbol_pair)
                
                if current_price:
                    pos_data["current_price"] = current_price
                    
                    # 计算剩余数量（考虑阶段性平仓）
                    closed_qty = row["closed_quantity"] if row["closed_quantity"] else 0
                    remaining_qty = row["quantity"] - closed_qty
                    
                    # Calculate unrealized PnL (基于剩余数量)
                    if row["direction"] == "LONG":
                        unrealized_pnl = remaining_qty * (current_price - row["entry_price"])
                    else:
                        unrealized_pnl = remaining_qty * (row["entry_price"] - current_price)
                    
                    pos_data["unrealized_pnl"] = round(unrealized_pnl, 2)
            
            positions.append(pos_data)
        
        return {"source": "virtual", "positions": positions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders")
def get_orders(user_id: str = None, limit: int = 20):
    """Get open orders - from Binance if configured, otherwise from local DB"""
    try:
        # 如果 user_id 提供且已配置 Binance，获取 Binance 订单
        if user_id:
            from binance_client import has_user_api_keys, get_user_trading_status, get_user_binance_client
            
            if has_user_api_keys(user_id):
                status = get_user_trading_status(user_id)
                if status.get("is_trading_enabled"):
                    client = get_user_binance_client(user_id)
                    if client:
                        try:
                            binance_orders = client.get_open_orders()
                            # 确保返回的是列表
                            if not isinstance(binance_orders, list):
                                if isinstance(binance_orders, dict) and "code" in binance_orders:
                                    print(f"[Strategy] Binance error: {binance_orders}")
                                    # Don't fallback silently if we know it's a Binance user
                                    return {"orders": [], "source": "binance_error", "error": str(binance_orders)}
                                binance_orders = [] # Unknown format
                            
                            if binance_orders: # Process if there are orders
                                formatted_orders = []
                            for order in binance_orders:
                                # 格式化 Binance 订单字段
                                order_type = order.get("type", "")
                                side = order.get("side", "")
                                
                                # 推断方向：对于止损/止盈订单，需要反推
                                if order_type in ["STOP_MARKET", "TAKE_PROFIT_MARKET"]:
                                    direction = "SHORT" if side == "BUY" else "LONG"
                                else:
                                    direction = "LONG" if side == "BUY" else "SHORT"
                                
                                # 确定订单动作
                                if order_type == "STOP_MARKET":
                                    action = "STOP_LOSS"
                                elif order_type == "TAKE_PROFIT_MARKET":
                                    action = "TAKE_PROFIT"
                                elif order_type == "LIMIT":
                                    action = f"LIMIT_{side}"
                                else:
                                    action = order_type
                                
                                formatted_orders.append({
                                    "id": order.get("orderId"),
                                    "order_id": order.get("orderId"),
                                    "symbol": order.get("symbol", "").replace("USDT", ""),
                                    "direction": direction,
                                    "action": action,
                                    "type": order_type,
                                    "side": side,
                                    "quantity": float(order.get("origQty", 0)),
                                    "price": float(order.get("price", 0)),
                                    "stop_price": float(order.get("stopPrice", 0)),
                                    "status": order.get("status"),
                                    "created_at": order.get("time"),
                                    "source": "binance"
                                })
                            
                            return {"orders": formatted_orders, "source": "binance"}
                        except Exception as e:
                            print(f"[Strategy] Binance get_orders error: {e}")
                            # Continue to fallback
        
        # 回退到本地数据库
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM orders ORDER BY created_at DESC LIMIT %s",
                (limit,)
            )
            rows = cursor.fetchall()
            
            orders = []
            for row in rows:
                order = dict(row)
                pos = None
                
                # 兼容旧订单：如果没有 direction，尝试从关联的 position 获取
                if not order.get("direction") and order.get("position_id"):
                    cursor.execute(
                        "SELECT direction, quantity FROM positions WHERE id = %s",
                        (order["position_id"],)
                    )
                    pos = cursor.fetchone()
                
                if pos:
                    order["direction"] = pos["direction"]
                    if order.get("action", "").startswith("OPEN") and not order.get("quantity"):
                        order["quantity"] = pos["quantity"]
            
                # 兼容旧订单：从 action 推断 direction
                if not order.get("direction"):
                    action = order.get("action", "")
                    if "LONG" in action:
                        order["direction"] = "LONG"
                    elif "SHORT" in action:
                        order["direction"] = "SHORT"
                
                order["source"] = "local"
                orders.append(order)
        
        conn.close()
        return {"orders": orders, "source": "local"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs")
def get_strategy_logs(limit: int = 10, offset: int = 0):
    """Get strategy logs with pagination support"""
    try:
        conn = get_db_connection()
        
        # Get total count for pagination
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM strategy_logs")
            total_count = cursor.fetchone()[0]
            
            # Get paginated logs
            cursor.execute(
                "SELECT * FROM strategy_logs ORDER BY timestamp DESC LIMIT %s OFFSET %s",
                (limit, offset)
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
    is_testnet: bool = True


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


