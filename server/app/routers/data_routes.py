"""
Strategy Data Routes - 数据查询路由
从 strategy.py 拆分而来：钱包/持仓/订单/交易历史等
"""
from fastapi import APIRouter, HTTPException
import os
from app.database import get_db_connection
from app.services.price_service import fetch_prices_batch

router = APIRouter()

STRATEGY_ADMIN_USER_ID = "ee20fa53-5ac2-44bc-9237-41b308e291d8"
BINANCE_API_BASE = os.getenv("BINANCE_API_BASE", "https://api.binance.com")

def _get_active_client(user_id: str):
    from app.services.workspace_service import list_trader_instances
    from tools.trading_tools import set_current_trader_id
    from tools.exchange_trading_tools import _get_trading_client
    instances = list_trader_instances(user_id)
    primary = next((i for i in instances if i.get("status") == "RUNNING"), None)
    if not primary:
        primary = instances[0] if instances else None
    exchange_account_id = None
    if primary and primary.get("exchange_account_id"):
        exchange_account_id = primary["exchange_account_id"]
        set_current_trader_id(primary["id"])
    client, err = _get_trading_client(user_id, require_trading_enabled=False)
    return client, err, exchange_account_id


def _get_user_platform_start_time(user_id: str, exchange_account_id: int = None) -> int:
    """
    获取用户绑定到平台的时间起点（毫秒级时间戳）。
    
    取以下两者中最早的时间：
    1. 当前 exchange_account 的 created_at
    2. strategy_logs.timestamp     — 该用户第一条策略日志的时间
    
    这样只统计"属于平台"的交易，避免拉取用户在绑定前的陈年历史。
    如果两者都查不到，返回 0（不做时间限制）。
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if exchange_account_id:
                cursor.execute("""
                    SELECT LEAST(
                        (SELECT created_at FROM exchange_accounts WHERE id = %s),
                        (SELECT MIN("timestamp"::timestamptz) FROM strategy_logs WHERE user_id = %s)
                    )
                """, (exchange_account_id, user_id))
            else:
                cursor.execute("""
                    SELECT LEAST(
                        (SELECT MIN(created_at) FROM exchange_accounts WHERE user_id = %s),
                        (SELECT MIN("timestamp"::timestamptz) FROM strategy_logs WHERE user_id = %s)
                    )
                """, (user_id, user_id))
            row = cursor.fetchone()
            if row and row[0]:
                val = row[0]
                if isinstance(val, str):
                    from datetime import datetime
                    val = datetime.fromisoformat(val)
                return int(val.timestamp() * 1000)
        return 0
    except Exception as e:
        print(f"[DataRoutes] Error getting platform start time for {user_id[:8]}: {e}")
        return 0
    finally:
        if conn:
            conn.close()


def _fetch_all_trades_since(client, symbol: str, start_time_ms: int, max_trades: int = 5000) -> list:
    """
    从指定时间点开始拉取所有交易记录，自动处理 Binance 7 天窗口限制。
    
    Binance API 规则：
    - startTime 不带 endTime → 只返回 startTime 起 7 天内的数据
    - startTime + endTime → 窗口不能超过 7 天
    - fromId → 无时间限制，从该 ID 往后取
    
    策略：
    1. 第一次调用用 startTime+endTime(7天) 取到第一批数据和 fromId 锚点
    2. 后续调用用 fromId 自动分页（无 7 天限制）直到取完
    
    对于非 Binance 交易所，直接用 start_time 单次调用。
    """
    import time

    if start_time_ms <= 0:
        # 没有平台起点，走默认行为
        return client.get_trade_history(symbol=symbol, limit=1000) or []

    is_binance = hasattr(client, 'get_exchange_name') and client.get_exchange_name() == 'Binance'

    if not is_binance:
        # OKX/Bitget 等交易所 start_time 支持 3 个月窗口，单次调用足够
        return client.get_trade_history(symbol=symbol, limit=1000, start_time=start_time_ms) or []

    # ===== Binance 分页策略 =====
    all_trades = []
    now_ms = int(time.time() * 1000)
    SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000

    # Step 1: 用 startTime + endTime 滑动窗口找到第一批数据（锚定 fromId）
    current_start = start_time_ms
    first_trade_found = False
    
    # 限制最多往前滑动查找 15 个周期 (约100天)，避免死循环或过多 API 调用
    for _ in range(15):
        if current_start > now_ms:
            break
            
        end_time = min(current_start + SEVEN_DAYS_MS, now_ms)
        trades = client.get_trade_history(
            symbol=symbol, limit=1000,
            start_time=current_start, end_time=end_time
        )
        
        if isinstance(trades, list) and len(trades) > 0:
            all_trades.extend(trades)
            first_trade_found = True
            break
            
        current_start += SEVEN_DAYS_MS

    if not first_trade_found:
        return []

    # Step 2: 用 fromId 分页取后续数据（突破 7 天限制）
    while len(all_trades) < max_trades:
        last_id = int(all_trades[-1].get("id", 0))
        if last_id <= 0:
            break

        trades = client.get_trade_history(
            symbol=symbol, limit=1000, fromId=last_id + 1
        )

        if not isinstance(trades, list) or not trades:
            break

        all_trades.extend(trades)

        # 如果返回不满页，说明已到末尾
        if len(trades) < 1000:
            break

    return all_trades


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
        client, err, exchange_account_id = _get_active_client(user_id)
        
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
            client, err, exchange_account_id = _get_active_client(user_id)
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
            client, err, exchange_account_id = _get_active_client(user_id)
            
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
        client, err, exchange_account_id = _get_active_client(user_id)
        
        if not client:
            return {"trades": [], "source": "exchange", "error": "No exchange account configured"}
            
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
        all_trades = []
        
        for symbol in symbol_list:
            # Add USDT if missing
            if not symbol.endswith("USDT"):
                symbol += "USDT"
                
            try:
                start_ts = _get_user_platform_start_time(user_id, exchange_account_id)
                trades = _fetch_all_trades_since(client, symbol, start_ts, max_trades=2000)
                
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
        client, err, exchange_account_id = _get_active_client(user_id)
        if err or not client:
            return {"positions": [], "error": err or "No active exchange account configured"}
        
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
        all_positions = []
        
        # 1. 检查是否有原生接口覆盖（只有子类真正实现了才使用，基类返回空列表不算）
        # 判断方式：子类是否覆盖了基类的 get_position_history
        from exchanges.base import ExchangeClient
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
                
                start_ts = _get_user_platform_start_time(user_id, exchange_account_id)
                trades = _fetch_all_trades_since(client, sym, start_ts, max_trades=5000)
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
        client, err, exchange_account_id = _get_active_client(user_id)
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
            # 仅按 user_id 进行严格数据隔离
            cursor.execute("SELECT COUNT(*) FROM strategy_logs WHERE user_id = %s", (user_id,))
            total_count = cursor.fetchone()[0]
            
            cursor.execute(
                "SELECT * FROM strategy_logs WHERE user_id = %s ORDER BY timestamp DESC LIMIT %s OFFSET %s",
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

import time
import requests
import concurrent.futures

_SYMBOLS_CACHE = {"data": [], "timestamp": 0}

@router.get("/symbols")
def get_tradable_symbols():
    """
    Get a list of all active USDT perpetual futures symbols from multiple exchanges.
    Results are cached for 1 hour to prevent rate limiting.
    """
    global _SYMBOLS_CACHE
    now = time.time()
    
    # Cache for 1 hour
    if now - _SYMBOLS_CACHE["timestamp"] < 3600 and _SYMBOLS_CACHE["data"]:
        return {"symbols": _SYMBOLS_CACHE["data"]}
        
    def fetch_binance():
        try:
            r = requests.get("https://fapi.binance.com/fapi/v1/exchangeInfo", timeout=5)
            return [{"exchange": "Binance", "symbol": sym["symbol"], "desc": "Binance USDT Perpetual"} 
                    for sym in r.json().get("symbols", []) 
                    if sym.get("status") == "TRADING" and sym.get("quoteAsset") == "USDT" and sym.get("contractType") == "PERPETUAL"]
        except: return []

    def fetch_okx():
        try:
            r = requests.get("https://www.okx.com/api/v5/public/instruments?instType=SWAP", timeout=5)
            # OKX swap symbols end with -SWAP, usually USDT swaps are like BTC-USDT-SWAP
            return [{"exchange": "OKX", "symbol": sym["instId"], "desc": "OKX USDT Swap"} 
                    for sym in r.json().get("data", []) 
                    if sym.get("state") == "live" and sym.get("settleCcy") == "USDT"]
        except: return []

    def fetch_bybit():
        try:
            r = requests.get("https://api.bybit.com/v5/market/instruments-info?category=linear", timeout=5)
            return [{"exchange": "Bybit", "symbol": sym["symbol"], "desc": "Bybit Linear Perpetual"} 
                    for sym in r.json().get("result", {}).get("list", []) 
                    if sym.get("status") == "Trading" and sym.get("quoteCoin") == "USDT"]
        except: return []

    def fetch_bitget():
        try:
            r = requests.get("https://api.bitget.com/api/v2/mix/market/contracts?productType=USDT-FUTURES", timeout=5)
            return [{"exchange": "Bitget", "symbol": sym["symbol"], "desc": "Bitget USDT Perpetual"} 
                    for sym in r.json().get("data", []) 
                    if sym.get("symbolStatus") == "normal"]
        except: return []

    def fetch_gate():
        try:
            r = requests.get("https://api.gateio.ws/api/v4/futures/usdt/contracts", timeout=5)
            return [{"exchange": "Gate", "symbol": sym["name"], "desc": "Gate USDT Futures"} 
                    for sym in r.json() 
                    if isinstance(sym, dict) and not sym.get("in_delisting")]
        except: return []

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(fetch_binance),
            executor.submit(fetch_okx),
            executor.submit(fetch_bybit),
            executor.submit(fetch_bitget),
            executor.submit(fetch_gate)
        ]
        for future in concurrent.futures.as_completed(futures):
            results.extend(future.result())

    if results:
        _SYMBOLS_CACHE = {
            "data": results,
            "timestamp": now
        }
    
    return {"symbols": _SYMBOLS_CACHE["data"] or [{"exchange": "Binance", "symbol": "BTCUSDT", "desc": "Binance USDT Perpetual"}]}
