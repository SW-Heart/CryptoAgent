"""
Strategy API router.
Handles virtual trading, positions, and strategy logs.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks

def _get_active_client(user_id: str):
    from app.services.workspace_service import list_trader_instances
    from tools.trading_tools import set_current_trader_id
    from tools.exchange_trading_tools import _get_trading_client
    
    instances = list_trader_instances(user_id)
    primary = next((i for i in instances if i.get("status") == "RUNNING"), None)
    if not primary:
        primary = instances[0] if instances else None
    
    if primary and primary.get("exchange_account_id"):
        set_current_trader_id(primary["id"])
    return _get_trading_client(user_id, require_trading_enabled=False)

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
            # strategy_logs extensions
            try:
                cursor.execute("ALTER TABLE strategy_logs ADD COLUMN IF NOT EXISTS user_id TEXT")
                cursor.execute("ALTER TABLE strategy_logs ADD COLUMN IF NOT EXISTS trader_instance_id TEXT")
            except Exception as e:
                print(f"[Strategy] strategy_logs migration note: {e}")
                
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
        from tools.exchange_trading_tools import get_positions_summary
        from binance_client import BinanceFuturesClient, has_user_api_keys
        # 1. 尝试从 Workspace 查找当前的实盘账户绑定
        client, err = _get_active_client(user_id)
        
        # 如果有关联的交易所账户，尝试获取真实余额
        if client:
            result = None
            last_exchange_error = None
            
            try:
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
                        "equity": balance.get("margin_balance", 0) if balance.get("margin_balance", 0) > 0 else balance.get("wallet_balance", 0) + total_unrealized,
                        "margin_in_use": round(total_margin, 2),
                        "balance_breakdown": balance.get("assets", [])
                    }
                else:
                    last_exchange_error = balance.get('error')
                    print(f"[Strategy] Workspace exchange balance error: {last_exchange_error}")
            except Exception as e:
                last_exchange_error = str(e)
                print(f"[Strategy] Error getting balance via active client: {e}")
                
            if result and "error" not in result:
                # 只如果是 binance，才走老的 local DB history aggregate
                total_pnl, total_trades, win_trades, win_rate = 0, 0, 0, 0
                if client.__class__.__name__ == "BinanceFuturesClient":
                    conn = get_db_connection()
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

                    if total_trades > 0:
                        win_rate = round(win_trades / total_trades * 100, 1)

                return {
                    "source": "exchange",
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
        symbols = []
        for pos in positions:
            sym = pos['symbol']
            if not sym.endswith("USDT"):
                sym = f"{sym}USDT"
            if sym not in symbols:
                symbols.append(sym)
                
        price_map = fetch_prices_batch(symbols, BINANCE_API_BASE)

        for pos in positions:
            total_margin_in_use += pos["margin"]
            # 计算剩余数量（原始数量 - 已平仓数量）
            closed_qty = pos["closed_quantity"] if pos["closed_quantity"] else 0
            remaining_qty = pos["quantity"] - closed_qty
            
            symbol_pair = pos['symbol']
            if not symbol_pair.endswith("USDT"):
                symbol_pair = f"{symbol_pair}USDT"
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
        """Convert get_positions_summary result to unified frontend format."""
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
    
    # 实盘数据获取
    if user_id:
        try:
            from tools.exchange_trading_tools import get_positions_summary
            # 使用提取出的公用方法获取最新 active_client
            client, err = _get_active_client(user_id)
            if client:
                result = get_positions_summary(user_id)
                if isinstance(result, dict) and "error" not in result:
                    return {"source": "exchange", "positions": _format_binance_positions(result)}
                else:
                    print(f"[Strategy] Positions via Workspace failed: {result.get('error', 'unknown') if isinstance(result, dict) else result}")
        except Exception as e:
            print(f"[Strategy] Exchange positions error: {e}")
    
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
        symbols = []
        for row in rows:
            if row["status"] == "OPEN":
                sym = row['symbol']
                if not sym.endswith("USDT"):
                    sym = f"{sym}USDT"
                if sym not in symbols:
                    symbols.append(sym)
                    
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
                symbol_pair = row['symbol']
                if not symbol_pair.endswith("USDT"):
                    symbol_pair = f"{symbol_pair}USDT"
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
                    if pos_data.get("margin"):
                        pos_data["roi_percent"] = round((unrealized_pnl / pos_data["margin"]) * 100, 2)
                    else:
                        pos_data["roi_percent"] = 0
            
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
        # 如果 user_id 提供，通过 _get_active_client 统一获取客户端
        if user_id:
            client, err = _get_active_client(user_id)
            
            if client:
                try:
                    exchange_orders = []
                    
                    if status == "OPEN":
                        exchange_orders = client.get_open_orders()
                        try:
                            # 尝试获取条件/算法订单
                            algo_orders = client.get_open_algo_orders() if hasattr(client, "get_open_algo_orders") else []
                            if isinstance(algo_orders, list):
                                if not isinstance(exchange_orders, list):
                                    exchange_orders = []
                                exchange_orders.extend(algo_orders)
                        except Exception as e:
                            print(f"[Strategy] Failed to fetch open algo orders: {e}")
                    else:
                        # History requires symbol iterations
                        symbol_list = [s.strip().upper() for s in symbols.split(",")]
                        for sym in symbol_list:
                            if not sym.endswith("USDT"):
                                sym += "USDT"
                            try:
                                sym_orders = client.get_order_history(symbol=sym, limit=limit)
                                if isinstance(sym_orders, list):
                                    exchange_orders.extend(sym_orders)
                            except Exception as e:
                                print(f"[Strategy] Error fetching order history for {sym}: {e}")
                        
                        # Sort combined history by time desc
                        exchange_orders.sort(key=lambda x: x.get("time", 0) or x.get("updateTime", 0), reverse=True)
                        exchange_orders = exchange_orders[:limit]

                    # 确保返回的是列表
                    if not isinstance(exchange_orders, list):
                        if isinstance(exchange_orders, dict) and "code" in exchange_orders:
                            return {"orders": [], "source": "exchange_error", "error": str(exchange_orders)}
                        exchange_orders = []
                    
                    # 提取当前用户的实际仓位大小，用于智能替换“全部平仓”条件单为确切的数量
                    pos_map = {}
                    try:
                        raw_positions = client.get_positions()
                        if isinstance(raw_positions, list):
                            for p in raw_positions:
                                sym_raw = p.get("symbol", "")
                                qty = abs(float(p.get("quantity", 0) or 0))
                                if qty > 0:
                                    direction = p.get("direction", "LONG")
                                    sym_short = sym_raw.replace("USDT", "").replace("-USDT-SWAP", "")
                                    pos_map[(sym_short, direction)] = qty
                    except Exception as e:
                        print(f"[Strategy] Error fetching positions for quantity deduction: {e}")
                    
                    formatted_orders = []
                    for order in exchange_orders:
                        side = order.get("side", "").upper()
                        
                        # 解析订单类型：尝试多个字段 (Binance 和 OKX)
                        order_type = order.get("type") or order.get("orderType") or order.get("ordType") or ""
                        order_type = order_type.upper()
                        
                        # Algo 订单可能没有具体 type，需要从触发条件推断
                        if not order_type or order_type == "CONDITIONAL":
                            algo_type = order.get("algoType", "")
                            if algo_type == "CONDITIONAL":
                                trigger_cond = order.get("triggerCondition", "")
                                if trigger_cond == "ge":
                                    order_type = "TAKE_PROFIT_MARKET" if side == "SELL" else "STOP_MARKET"
                                elif trigger_cond == "le":
                                    order_type = "STOP_MARKET" if side == "SELL" else "TAKE_PROFIT_MARKET"
                                else:
                                    book_side = order.get("bookSide", "")
                                    order_type = f"CONDITIONAL_{book_side}" if book_side else "CONDITIONAL"
                            elif algo_type:
                                order_type = algo_type
                        
                        is_reduce = str(order.get("reduceOnly", "")).lower() == "true"
                        is_close_position = str(order.get("closePosition", "")).lower() == "true"
                        is_conditional = order_type in ("STOP_MARKET", "TAKE_PROFIT_MARKET", "STOP", "TAKE_PROFIT", "TRAILING_STOP_MARKET")
                        
                        # 币安和OKX对于“全部平仓”数量往往为0，需要特殊处理
                        try:
                            orig_qty_val = float(order.get("origQty", 0.0) or 0.0)
                        except:
                            orig_qty_val = 0.0
                            
                        if is_conditional and orig_qty_val == 0.0:
                            is_close_position = True
                            
                        # 智能数量补偿：如果返回值为0 且属于平仓动作，根据当前仓位大小自动填充真实数量
                        if orig_qty_val == 0.0 and (is_close_position or is_reduce):
                            sym = order.get("symbol", "").replace("USDT", "").replace("-USDT-SWAP", "")
                            target_direction = "LONG" if side == "SELL" else "SHORT"
                            deduced_qty = pos_map.get((sym, target_direction), 0.0)
                            if deduced_qty > 0:
                                orig_qty_val = deduced_qty
                                # 当已经通过仓位填补了数字后，不再强制显示全部平仓，而是显示出精确数字
                                is_close_position = False 
                        
                        # 判断方向：条件单/reduceOnly 是平仓单
                        if is_reduce or is_close_position or is_conditional:
                            # SELL = 平多仓, BUY = 平空仓
                            direction = "CLOSE_LONG" if side == "SELL" else "CLOSE_SHORT"
                        else:
                            direction = "LONG" if side == "BUY" else "SHORT"
                        
                        # 订单类型中文映射
                        type_map = {
                            "STOP_MARKET": "市价止损",
                            "TAKE_PROFIT_MARKET": "市价止盈",
                            "LIMIT": "限价委托",
                            "TRAILING_STOP_MARKET": "跟踪止损",
                            "STOP": "限价止损",
                            "TAKE_PROFIT": "限价止盈",
                            "MARKET": "市价委托",
                            "CONDITIONAL": "条件委托",
                        }
                        action = type_map.get(order_type, order_type or "未知")
                        
                        def safe_float(v):
                            if v is None or v == "": return 0.0
                            try: return float(v)
                            except: return 0.0

                        status_val = order.get("status") or order.get("algoStatus")
                        if status_val == "WORKING":
                            status_val = "NEW"

                        formatted_orders.append({
                            "id": order.get("orderId") or order.get("algoId"),
                            "order_id": order.get("orderId") or order.get("algoId"),
                            "symbol": order.get("symbol", "").replace("USDT", ""),
                            "direction": direction,
                            "action": action,
                            "type": order_type,
                            "quantity": orig_qty_val,
                            "executed_quantity": safe_float(order.get("executedQty")),
                            "price": safe_float(order.get("price")),
                            "stop_price": safe_float(order.get("stopPrice") or order.get("triggerPrice")),
                            "activation_price": safe_float(order.get("activationPrice")),
                            "callback_rate": safe_float(order.get("callbackRate")),
                            "time": order.get("time") or order.get("updateTime"),
                            "status": status_val,
                            "reduce_only": is_reduce,
                            "close_position": is_close_position
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

    # Fetch from Exchange
    try:
        client, err = _get_active_client(user_id)
        
        if not client:
            return {"trades": [], "source": "exchange", "error": "No exchange account configured"}
            
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
                        # 客户端层已统一格式化，直接读取标准字段
                        all_trades.append({
                            "id": t.get("id"),
                            "order_id": t.get("orderId"),
                            "symbol": t.get("symbol"),
                            "side": t.get("side", ""),
                            "position_side": t.get("positionSide", ""),
                            "price": t.get("price", 0),
                            "quantity": t.get("qty", 0),
                            "quote_quantity": t.get("quoteQty", 0),
                            "realized_pnl": t.get("realizedPnl", 0),
                            "commission": t.get("commission", 0),
                            "commission_asset": t.get("commissionAsset", "USDT"),
                            "time": t.get("time", 0),
                            "maker": t.get("maker"),
                            "source": "exchange"
                        })
            except Exception as e:
                print(f"[Strategy] Error fetching trades for {symbol}: {e}")
                
        # Sort by time descending
        all_trades.sort(key=lambda x: x["time"], reverse=True)
        
        return {"trades": all_trades, "source": "exchange"}
        
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
        # 统一使用 _get_active_client 获取当前实盘实例上下文
        client, err = _get_active_client(user_id)
        if err or not client:
            return {"positions": [], "error": err or "No active exchange account configured"}
        
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
        all_positions = []
        
        # 1. 检查是否有原生接口覆盖（只有子类真正实现了才使用，基类返回空列表不算）
        # 判断方式：子类是否覆盖了基类的 get_position_history
        from exchange_base import ExchangeClient
        has_native = type(client).get_position_history is not ExchangeClient.get_position_history
        
        for sym in symbol_list:
            if not sym.endswith("USDT"):
                sym += "USDT"
            
            if has_native:
                try:
                    native_pos = client.get_position_history(symbol=sym, limit=limit)
                    if isinstance(native_pos, list) and native_pos:
                        all_positions.extend(native_pos)
                        continue  # 有原生数据，跳过 trade 聚合
                except Exception as e:
                    print(f"[Strategy] Native get_position_history for {sym} failed: {e}")
                
            # 2. Fallback: 使用 position_builder 从 trades 聚合
            try:
                from position_builder import build_position_history
                
                trades = client.get_trade_history(symbol=sym, limit=min(limit * 5, 500))
                if isinstance(trades, list):
                    closed_positions = build_position_history(
                        trades=trades,
                        symbol=sym,
                        default_leverage=10,
                    )
                    all_positions.extend(closed_positions)
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
        client, err = _get_active_client(user_id)
        if err or not client:
            return {"records": [], "error": err or "No active exchange account"}
        
        # 直接调用客户端的统一接口
        records = client.get_income_history(
            symbol=symbol,
            income_type=income_type,
            limit=limit
        )
        
        if isinstance(records, dict) and "error" in records:
            raise HTTPException(status_code=400, detail=records["error"])
        
        return {"records": records or [], "source": "exchange"}
        
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
        from tools.exchange_trading_tools import get_funding_rate
        
        result = get_funding_rate(
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
        from tools.exchange_trading_tools import get_adl_risk
        result = get_adl_risk(user_id=user_id)
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
        from tools.exchange_trading_tools import get_force_orders
        result = get_force_orders(symbol=symbol, limit=limit, user_id=user_id)
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
        from tools.exchange_trading_tools import get_leverage_info
        result = get_leverage_info(symbol=symbol, user_id=user_id)
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
        from tools.exchange_trading_tools import get_commission_rate
        result = get_commission_rate(symbol=symbol, user_id=user_id)
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
        from tools.exchange_trading_tools import place_trailing_stop
        result = place_trailing_stop(
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
        from tools.exchange_trading_tools import get_position_mode
        result = get_position_mode(user_id=user_id)
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
        from tools.exchange_trading_tools import change_position_mode
        result = change_position_mode(dual_side=dual_side, user_id=user_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
