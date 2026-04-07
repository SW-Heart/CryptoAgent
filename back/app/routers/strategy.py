"""
Strategy API router.
Handles virtual trading, positions, and strategy logs.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
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
                user_id TEXT UNIQUE,
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
                user_id TEXT,
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
        
        # Binance sync state table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS binance_sync_state (
                user_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                last_trade_id BIGINT DEFAULT 0,
                total_pnl DOUBLE PRECISION DEFAULT 0,
                total_trades INTEGER DEFAULT 0,
                win_trades INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, symbol)
            )
        """)
        conn.commit()
    
    # Initialize wallet if not exists
    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO virtual_wallet (id, user_id, initial_balance, current_balance)
            VALUES (1, %s, 10000, 10000)
            ON CONFLICT (id) DO NOTHING
        """, (STRATEGY_ADMIN_USER_ID,))
        conn.commit()
    conn.close()
    
    # Run migrations
    migrate_tables()

def migrate_tables():
    """Migrate tables to add missing columns"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            print("[Strategy] Checking migrations...")
            
            # Virtual wallet user_id
            try:
                cursor.execute("ALTER TABLE virtual_wallet ADD COLUMN IF NOT EXISTS user_id TEXT UNIQUE")
            except Exception as e:
                # Fallback for older Postgres versions if needed, or ignore if exists
                print(f"[Strategy] virtual_wallet migration note: {e}")
            
            # Fix data: ensure ID 1 has user_id
            cursor.execute("UPDATE virtual_wallet SET user_id = %s WHERE id = 1 AND user_id IS NULL", (STRATEGY_ADMIN_USER_ID,))
            
            # Positions user_id
            try:
                cursor.execute("ALTER TABLE positions ADD COLUMN IF NOT EXISTS user_id TEXT")
            except Exception as e:
                 print(f"[Strategy] positions migration note: {e}")

            # Fix data: populate missing user_ids
            cursor.execute("UPDATE positions SET user_id = %s WHERE user_id IS NULL", (STRATEGY_ADMIN_USER_ID,))
            
            print("[Strategy] Migrations completed")
                
        conn.commit()
    except Exception as e:
        print(f"[Strategy] Migration error: {e}")
    finally:
        conn.close()

# GET endpoints for UI

@router.get("/wallet")
def get_wallet(user_id: str = None):
    """Get wallet status with real-time equity.
    
    If user has a Workspace instance linked to a real exchange account,
    returns real data from that exchange.
    Otherwise returns virtual trading data (demo mode).
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
        
    try:
        from app.services.workspace_service import list_trader_instances, list_exchange_accounts, _normalize_json
        from tools.binance_trading_tools import binance_get_positions_summary
        from binance_client import BinanceFuturesClient, has_user_api_keys
        
        # 1. 尝试从 Workspace 查找当前的实盘账户绑定
        instances = list_trader_instances(user_id)
        primary = next((i for i in instances if i["slug"] == "primary-runtime"), None)
        if not primary:
            primary = instances[0] if instances else None
        
        exchange_account_id = primary.get("exchange_account_id") if primary else None
        
        # 如果有关联的交易所账户，尝试获取真实余额
        if exchange_account_id:
            result = None
            last_exchange_error = None
            
            # 路径 A: 优先尝试旧版 Binance 密钥（user_binance_keys 表）
            if has_user_api_keys(user_id):
                result = binance_get_positions_summary(user_id)
                if "error" in result:
                    last_exchange_error = result.get("error")
                    result = None
            
            # 路径 B: 回退到 Workspace 交易所账户凭证（exchange_accounts.metadata_json）
            if result is None:
                try:
                    # 直接从数据库读取原始凭证（可能已加密），而非通过脱敏的 list 接口
                    conn_ws = get_db_connection()
                    try:
                        with conn_ws.cursor() as ws_cursor:
                            ws_cursor.execute(
                                "SELECT metadata_json, environment FROM exchange_accounts WHERE id = %s AND user_id = %s",
                                (exchange_account_id, user_id)
                            )
                            ea_row = ws_cursor.fetchone()
                    finally:
                        conn_ws.close()
                    
                    if ea_row:
                        meta = _normalize_json(ea_row["metadata_json"]) if ea_row["metadata_json"] else {}
                        raw_key = meta.get("api_key", "")
                        raw_secret = meta.get("api_secret", "")
                        environment = ea_row.get("environment", "demo")
                        is_testnet = environment in ("testnet", "demo")
                        
                        # 解密凭证（如果已加密）
                        api_key = raw_key
                        api_secret = raw_secret
                        if raw_key and raw_key.startswith("gAAAA"):
                            try:
                                from binance_client import decrypt_value
                                api_key = decrypt_value(raw_key)
                            except Exception as dec_e:
                                print(f"[Strategy] Failed to decrypt api_key for account {exchange_account_id}: {dec_e}")
                                api_key = ""
                        if raw_secret and raw_secret.startswith("gAAAA"):
                            try:
                                from binance_client import decrypt_value
                                api_secret = decrypt_value(raw_secret)
                            except Exception as dec_e:
                                print(f"[Strategy] Failed to decrypt api_secret for account {exchange_account_id}: {dec_e}")
                                api_secret = ""
                        
                        if api_key and api_secret:
                            client = BinanceFuturesClient(
                                api_key=api_key,
                                api_secret=api_secret,
                                testnet=is_testnet
                            )
                            balance = client.get_usdt_balance()
                            if "error" not in balance:
                                positions = client.get_positions()
                                open_positions = positions if isinstance(positions, list) else []
                                total_margin = 0
                                total_unrealized = balance.get("unrealized_pnl", 0)
                                for pos in open_positions:
                                    entry_price = pos.get("entry_price", 0)
                                    quantity = pos.get("quantity", 0)
                                    leverage = pos.get("leverage", 10)
                                    notional = quantity * entry_price
                                    margin = notional / leverage if leverage > 0 else notional
                                    total_margin += margin
                                
                                result = {
                                    "wallet_balance": balance.get("wallet_balance", 0),
                                    "margin_balance": balance.get("margin_balance", 0),
                                    "available_balance": balance.get("available_balance", 0),
                                    "unrealized_pnl": total_unrealized,
                                    "equity": balance.get("margin_balance", 0),
                                    "margin_in_use": round(total_margin, 2),
                                    "balance_breakdown": balance.get("assets", [])
                                }
                            else:
                                last_exchange_error = balance.get('error')
                                print(f"[Strategy] Workspace exchange balance error: {last_exchange_error}")
                        else:
                            last_exchange_error = f"Workspace exchange account {exchange_account_id} has no API credentials in metadata"
                            print(f"[Strategy] {last_exchange_error}")
                except Exception as ws_e:
                    last_exchange_error = str(ws_e)
                    print(f"[Strategy] Workspace exchange fallback error: {ws_e}")
            
            if result and "error" not in result:
                # 获取数据库记录的累计盈亏统计
                conn = get_db_connection()
                total_pnl = 0
                total_trades = 0
                win_trades = 0
                try:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            SELECT SUM(total_pnl), SUM(total_trades), SUM(win_trades)
                            FROM binance_sync_state
                            WHERE user_id = %s
                        """, (user_id,))
                        row = cursor.fetchone()
                        if row and row[0] is not None:
                            total_pnl = row[0]
                            total_trades = row[1]
                            win_trades = row[2]
                except Exception as db_e:
                    print(f"[Strategy] Error fetching stats: {db_e}")
                finally:
                    conn.close()

                win_rate = 0
                if total_trades > 0:
                    win_rate = round(win_trades / total_trades * 100, 1)

                return {
                    "source": "binance",
                    "initial_balance": None,
                    "current_balance": result.get("wallet_balance", 0),
                    "available_balance": result.get("available_balance", 0),
                    "margin_in_use": result.get("margin_in_use", 0),
                    "unrealized_pnl": result.get("unrealized_pnl", 0),
                    "equity": result.get("equity", 0),
                    "total_pnl": round(total_pnl, 2),
                    "total_trades": total_trades,
                    "win_trades": win_trades,
                    "win_rate": win_rate,
                    "balance_breakdown": result.get("balance_breakdown", [])
                }
            
            # 真实交易所已配置但临时无法获取数据 → 不要跌落到虚拟钱包！
            # 返回错误状态，让前端保持上次已知的余额
            if last_exchange_error:
                print(f"[Strategy] Exchange configured but temporarily unavailable, NOT falling back to virtual wallet")
                return {
                    "source": "binance_error",
                    "error": last_exchange_error,
                    "message": "Exchange temporarily unavailable, please retry"
                }
    except Exception as e:
        print(f"[Strategy] Wallet check error: {e}")

    # 2. 虚拟交易模式（Demo）- 作为最终回退方案
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
    
    Supports both legacy (user_binance_keys) and new Workspace (exchange_accounts) systems.
    """
    import requests
    
    def _format_binance_positions(result):
        """Convert binance_get_positions_summary result to unified frontend format."""
        positions = []
        for pos in result.get("open_positions", []):
            positions.append({
                "id": None,
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
        return positions
    
    # 如果用户启用了 Binance 交易，使用 Binance 数据
    if user_id:
        try:
            from tools.binance_trading_tools import binance_get_positions_summary, _get_trading_client
            from binance_client import get_user_trading_status, has_user_api_keys
            
            # 路径 A: 旧系统 (user_binance_keys + user_trading_status)
            if has_user_api_keys(user_id):
                trading_status = get_user_trading_status(user_id)
                if trading_status.get("is_configured") and trading_status.get("is_trading_enabled"):
                    result = binance_get_positions_summary(user_id)
                    if "error" not in result:
                        return {"source": "binance", "positions": _format_binance_positions(result)}
            
            # 路径 B: 新系统 Workspace (exchange_accounts)
            # 查看是否有关联的 exchange_account
            from app.services.workspace_service import list_trader_instances
            instances = list_trader_instances(user_id)
            primary = next((i for i in instances if i["slug"] == "primary-runtime"), None)
            if not primary:
                primary = instances[0] if instances else None
            
            if primary and primary.get("exchange_account_id"):
                # 使用 _get_trading_client 统一获取 client (支持双路径)
                result = binance_get_positions_summary(user_id)
                if isinstance(result, dict) and "error" not in result:
                    return {"source": "binance", "positions": _format_binance_positions(result)}
                else:
                    print(f"[Strategy] Binance positions via Workspace failed: {result.get('error', 'unknown') if isinstance(result, dict) else result}")
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
def get_orders(user_id: str = None, limit: int = 20, status: str = "OPEN", symbols: str = "BTCUSDT,ETHUSDT,SOLUSDT"):
    """
    Get orders - from Binance if configured, otherwise from local DB
    
    Args:
        user_id: User ID
        limit: Max orders to return
        status: "OPEN" or "HISTORY"
        symbols: Comma-separated symbols for history lookup (Binance requires symbol for history)
    """
    try:
        # 如果 user_id 提供且已配置 Binance，获取 Binance 订单
        if user_id:
            client = None
            
            # 路径 A: 旧系统 (user_binance_keys)
            from binance_client import has_user_api_keys, get_user_trading_status, get_user_binance_client
            if has_user_api_keys(user_id):
                trading_status = get_user_trading_status(user_id)
                if trading_status.get("is_configured"):
                    client = get_user_binance_client(user_id)
            
            # 路径 B: 新系统 Workspace (exchange_accounts)
            if not client:
                try:
                    from tools.binance_trading_tools import _get_trading_client
                    client, err = _get_trading_client(user_id, require_trading_enabled=False)
                    if err:
                        client = None
                except Exception:
                    client = None
            
            if client:
                try:
                    binance_orders = []
                    
                    if status == "OPEN":
                        binance_orders = client.get_open_orders()
                    else:
                        # History requires symbol iterations
                        symbol_list = [s.strip().upper() for s in symbols.split(",")]
                        for sym in symbol_list:
                            if not sym.endswith("USDT"):
                                sym += "USDT"
                            try:
                                sym_orders = client.get_order_history(symbol=sym, limit=limit)
                                if isinstance(sym_orders, list):
                                    binance_orders.extend(sym_orders)
                            except Exception as e:
                                print(f"[Strategy] Error fetching order history for {sym}: {e}")
                        
                        # Sort combined history by time desc
                        binance_orders.sort(key=lambda x: x.get("time", 0), reverse=True)
                        binance_orders = binance_orders[:limit]

                    # 确保返回的是列表
                    if not isinstance(binance_orders, list):
                        if isinstance(binance_orders, dict) and "code" in binance_orders:
                            print(f"[Strategy] Binance error: {binance_orders}")
                            return {"orders": [], "source": "binance_error", "error": str(binance_orders)}
                        binance_orders = []
                    
                    formatted_orders = []
                    for order in binance_orders:
                        order_type = order.get("type", "")
                        side = order.get("side", "")
                        
                        if order_type in ["STOP_MARKET", "TAKE_PROFIT_MARKET"]:
                            direction = "SHORT" if side == "BUY" else "LONG"
                        else:
                            direction = "LONG" if side == "BUY" else "SHORT"
                        
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
                            "filled_quantity": float(order.get("executedQty", 0)),
                            "price": float(order.get("price", 0)),
                            "avg_price": float(order.get("avgPrice", 0)),
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


@router.get("/trade-history")
def get_trade_history(user_id: str = None, symbols: str = "BTCUSDT,ETHUSDT,SOLUSDT", limit: int = 50):
    """
    Get trade history from Binance (Realan executed trades).
    
    Args:
        user_id: User ID (required for Binance API)
        symbols: Comma-separated list of symbols (e.g. "BTCUSDT,ETHUSDT")
        limit: Number of trades per symbol
    """
    if not user_id:
        # Fallback to local DB for demo/virtual users
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM orders WHERE status = 'FILLED' ORDER BY created_at DESC LIMIT %s",
                    (limit,)
                )
                rows = cursor.fetchall()
            conn.close()
            
            trades = []
            for row in rows:
                trade = dict(row)
                trade["source"] = "local_virtual"
                trades.append(trade)
            return {"trades": trades, "source": "local_virtual"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Fetch from Binance
    try:
        from binance_client import has_user_api_keys, get_user_binance_client
        
        client = None
        
        # 路径 A: 旧系统
        if has_user_api_keys(user_id):
            client = get_user_binance_client(user_id)
        
        # 路径 B: 新系统 Workspace
        if not client:
            try:
                from tools.binance_trading_tools import _get_trading_client
                client, err = _get_trading_client(user_id, require_trading_enabled=False)
                if err:
                    client = None
            except Exception:
                client = None
        
        if not client:
            return {"trades": [], "source": "binance", "error": "No exchange account configured"}
            
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
        all_trades = []
        
        for symbol in symbol_list:
            # Add USDT if missing
            if not symbol.endswith("USDT"):
                symbol += "USDT"
                
            try:
                trades = client.get_trade_history(symbol=symbol, limit=limit)
                
                if isinstance(trades, list):
                    for t in trades:
                        # Normalize fields
                        all_trades.append({
                            "id": t.get("id"),
                            "order_id": t.get("orderId"),
                            "symbol": t.get("symbol"),
                            "side": t.get("side"),
                            "price": float(t.get("price", 0)),
                            "quantity": float(t.get("qty", 0)),
                            "quote_quantity": float(t.get("quoteQty", 0)),
                            "realized_pnl": float(t.get("realizedPnl", 0)),
                            "commission": float(t.get("commission", 0)),
                            "commission_asset": t.get("commissionAsset"),
                            "time": t.get("time"),
                            "position_side": t.get("positionSide"),
                            "maker": t.get("maker"),
                            "source": "binance"
                        })
            except Exception as e:
                print(f"[Strategy] Error fetching trades for {symbol}: {e}")
                # Continue to next symbol
                
        # Sort by time descending
        all_trades.sort(key=lambda x: x["time"], reverse=True)
        
        return {"trades": all_trades, "source": "binance"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/position-history")
def get_position_history(
    user_id: str = None,
    symbols: str = "BTCUSDT,ETHUSDT,SOLUSDT",
    limit: int = 20
):
    """
    获取仓位历史（从交易记录聚合出仓位级别数据）。
    
    模拟 Binance 仓位历史页面的数据：
    - 每个仓位从开仓到平仓的完整生命周期
    - 包括已实现盈亏、收益率、开/平仓价格、数量、时间等
    
    Args:
        user_id: User ID (required)
        symbols: 逗号分隔的交易对列表
        limit: 每个交易对获取的最大交易数
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    
    try:
        from tools.binance_trading_tools import _get_trading_client
        
        client, err = _get_trading_client(user_id, require_trading_enabled=False)
        if err:
            return {"positions": [], "error": err}
        
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
        all_positions = []
        
        for sym in symbol_list:
            if not sym.endswith("USDT"):
                sym += "USDT"
            
            try:
                trades = client.get_trade_history(symbol=sym, limit=min(limit * 5, 500))
                if not isinstance(trades, list):
                    continue
                
                # 按时间正序排列以便追踪仓位生命周期
                trades.sort(key=lambda x: x.get("time", 0))
                
                # 追踪仓位状态，将交易聚合成仓位周期
                current_pos = None  # 当前追踪的仓位
                
                for trade in trades:
                    side = trade.get("side", "")
                    qty = float(trade.get("qty", 0))
                    price = float(trade.get("price", 0))
                    r_pnl = float(trade.get("realizedPnl", 0))
                    commission = float(trade.get("commission", 0))
                    trade_time = trade.get("time", 0)
                    
                    if current_pos is None:
                        # 开新仓
                        current_pos = {
                            "symbol": sym,
                            "direction": "LONG" if side == "BUY" else "SHORT",
                            "entry_trades": [],
                            "close_trades": [],
                            "total_entry_qty": 0,
                            "total_entry_cost": 0,
                            "total_close_qty": 0,
                            "total_close_cost": 0,
                            "realized_pnl": 0,
                            "total_commission": 0,
                            "open_time": trade_time,
                            "close_time": None,
                            "leverage": 10,  # 默认值
                        }
                    
                    # 判断这笔交易是开仓还是平仓
                    is_opening = (current_pos["direction"] == "LONG" and side == "BUY") or \
                                 (current_pos["direction"] == "SHORT" and side == "SELL")
                    
                    if is_opening:
                        current_pos["total_entry_qty"] += qty
                        current_pos["total_entry_cost"] += qty * price
                        current_pos["entry_trades"].append(trade)
                    else:
                        current_pos["total_close_qty"] += qty
                        current_pos["total_close_cost"] += qty * price
                        current_pos["close_trades"].append(trade)
                        current_pos["realized_pnl"] += r_pnl
                        current_pos["close_time"] = trade_time
                    
                    current_pos["total_commission"] += commission
                    
                    # 如果已平仓量 >= 开仓量，这个仓位周期结束
                    if current_pos["total_close_qty"] > 0 and \
                       current_pos["total_close_qty"] >= current_pos["total_entry_qty"] * 0.99:  # 0.99 容差
                        
                        entry_price = current_pos["total_entry_cost"] / current_pos["total_entry_qty"] \
                            if current_pos["total_entry_qty"] > 0 else 0
                        close_price = current_pos["total_close_cost"] / current_pos["total_close_qty"] \
                            if current_pos["total_close_qty"] > 0 else 0
                        
                        # 计算收益率 (基于开仓成本)
                        entry_notional = current_pos["total_entry_qty"] * entry_price
                        margin = entry_notional / current_pos["leverage"] if current_pos["leverage"] > 0 else entry_notional
                        roi = (current_pos["realized_pnl"] / margin * 100) if margin > 0 else 0
                        
                        all_positions.append({
                            "symbol": sym.replace("USDT", ""),
                            "symbol_full": sym,
                            "direction": current_pos["direction"],
                            "leverage": current_pos["leverage"],
                            "margin_mode": "全仓",
                            "close_type": "全部平仓",
                            "realized_pnl": round(current_pos["realized_pnl"], 4),
                            "roi_percent": round(roi, 2),
                            "closed_quantity": current_pos["total_close_qty"],
                            "entry_price": round(entry_price, 2),
                            "close_price": round(close_price, 2),
                            "max_quantity": current_pos["total_entry_qty"],
                            "total_commission": round(current_pos["total_commission"], 4),
                            "open_time": current_pos["open_time"],
                            "close_time": current_pos["close_time"],
                        })
                        
                        current_pos = None  # 重置，等待下一个仓位周期
                
            except Exception as e:
                print(f"[Strategy] Error building position history for {sym}: {e}")
        
        # 按平仓时间倒序排列
        all_positions.sort(key=lambda x: x.get("close_time", 0), reverse=True)
        all_positions = all_positions[:limit]
        
        return {"positions": all_positions, "source": "binance"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/income-history")
def get_income_history(
    user_id: str = None,
    symbol: str = None,
    income_type: str = None,
    limit: int = 50
):
    """
    获取收益历史记录（资金费率、已实现盈亏、手续费等）。
    
    Args:
        user_id: User ID (required)
        symbol: 交易对 (可选，如 "BTCUSDT")
        income_type: 收益类型 (可选: REALIZED_PNL, FUNDING_FEE, COMMISSION, TRANSFER)
        limit: 返回数量 (默认50，最大1000)
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    
    try:
        from tools.binance_trading_tools import binance_get_income_history
        
        result = binance_get_income_history(
            symbol=symbol,
            income_type=income_type,
            limit=limit,
            user_id=user_id
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/funding-rate")
def get_funding_rate(symbol: str, limit: int = 10, user_id: str = None):
    """
    获取资金费率历史。
    
    Args:
        symbol: 交易对 (如 "BTCUSDT" 或 "BTC")
        limit: 返回数量 (默认10)
        user_id: User ID (可选)
    """
    try:
        from tools.binance_trading_tools import binance_get_funding_rate
        
        result = binance_get_funding_rate(
            symbol=symbol,
            limit=limit,
            user_id=user_id
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/adl-risk")
def get_adl_risk(user_id: str):
    """获取 ADL (自动减仓) 风险等级。"""
    try:
        from tools.binance_trading_tools import binance_get_adl_risk
        result = binance_get_adl_risk(user_id=user_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/force-orders")
def get_force_orders(user_id: str, symbol: str = None, limit: int = 20):
    """获取强平订单历史。"""
    try:
        from tools.binance_trading_tools import binance_get_force_orders
        result = binance_get_force_orders(symbol=symbol, limit=limit, user_id=user_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leverage-bracket")
def get_leverage_bracket(user_id: str, symbol: str = None):
    """获取杠杆档位信息。"""
    try:
        from tools.binance_trading_tools import binance_get_leverage_info
        result = binance_get_leverage_info(symbol=symbol, user_id=user_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/commission-rate")
def get_commission_rate_api(user_id: str, symbol: str):
    """获取佣金费率。"""
    try:
        from tools.binance_trading_tools import binance_get_commission_rate
        result = binance_get_commission_rate(symbol=symbol, user_id=user_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trailing-stop")
def place_trailing_stop(
    user_id: str,
    symbol: str,
    callback_rate: float,
    quantity: float = None,
    close_percent: float = 100,
    activation_price: float = None
):
    """设置跟踪止损订单。"""
    try:
        from tools.binance_trading_tools import binance_place_trailing_stop
        result = binance_place_trailing_stop(
            symbol=symbol,
            callback_rate=callback_rate,
            quantity=quantity,
            close_percent=close_percent,
            activation_price=activation_price,
            user_id=user_id
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/position-mode")
def get_position_mode(user_id: str):
    """获取当前持仓模式。"""
    try:
        from tools.binance_trading_tools import binance_get_position_mode
        result = binance_get_position_mode(user_id=user_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/position-mode")
def change_position_mode(user_id: str, dual_side: bool):
    """切换持仓模式（需先平掉所有仓位）。"""
    try:
        from tools.binance_trading_tools import binance_change_position_mode
        result = binance_change_position_mode(dual_side=dual_side, user_id=user_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
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

@router.delete("/logs")
def clear_strategy_logs():
    """Clear all strategy logs"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM strategy_logs")
            conn.commit()
        conn.close()
        return {"success": True, "message": "Strategy logs cleared successfully"}
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
