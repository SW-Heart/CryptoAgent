"""
Exchange Trading Tools for Strategy Nexus
Unified trading operations for all supported exchanges (Binance, OKX, etc.)

This module provides exchange-agnostic trading operations using the unified
ExchangeClient interface. The actual exchange client is resolved at runtime
via exchange_factory based on the user's configured exchange account.

IMPORTANT: These functions use thread-local context to get user_id.
Call trading_tools.set_current_user(user_id) before using these tools.
"""
import os
from datetime import datetime
from typing import Optional, Dict, List, Any

from binance_client import (
    get_user_binance_client,
    get_user_trading_status,
    has_user_api_keys,
    BinanceFuturesClient
)

# Import context management from trading_tools
from tools.trading_tools import get_current_user, STRATEGY_ADMIN_USER_ID


def _get_effective_user_id(user_id: str = None) -> str:
    """
    Get effective user ID from parameter or thread context.
    Falls back to admin user if not set.
    
    Important: Filters out invalid placeholder values like "user" that
    LLMs sometimes generate incorrectly.
    """
    # Filter out invalid placeholder values that LLM might generate
    invalid_values = {"user", "user_id", ""}
    if user_id and user_id.lower() not in invalid_values and len(user_id) >= 10:
        return user_id
    
    # Fall back to context
    context_user = get_current_user()
    if context_user:
        return context_user
    
    return STRATEGY_ADMIN_USER_ID


def _get_trading_client(user_id: str, require_trading_enabled: bool = True):
    """
    统一获取 Binance Client 的入口（支持双路径）。

    路径 A: user_binance_keys 表 + user_trading_status 表（旧系统）
    路径 B: exchange_accounts 表（Workspace 新系统）

    Args:
        user_id: 用户 ID
        require_trading_enabled: 是否检查 is_trading_enabled（下单类操作需要，查询类不需要）

    Returns:
        (client, None) on success
        (None, error_message) on failure
    """
    # ===== 路径 A: 旧系统 =====
    if has_user_api_keys(user_id):
        if require_trading_enabled:
            status = get_user_trading_status(user_id)
            if not status.get("is_trading_enabled"):
                return None, "Trading is not enabled. Please enable trading first."
        client = get_user_binance_client(user_id)
        if client:
            return client, None
        return None, "Failed to create Binance client"

    # ===== 路径 B: 新系统 exchange_accounts =====
    try:
        from app.database import get_db_connection
        from tools.trading_tools import get_current_trader_id
        
        trader_id = None
        try:
            trader_id = get_current_trader_id()
        except Exception:
            pass

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                ea_row = None
                
                # 1. 优先通过上下文中获取到的 trader_id 精准锁定绑定的交易所账户
                if trader_id:
                    cur.execute('''
                        SELECT ea.id, ea.provider, ea.metadata_json, ea.environment
                        FROM trader_instances ti
                        JOIN exchange_accounts ea ON ea.id = ti.exchange_account_id
                        WHERE ti.id = %s AND ti.user_id = %s
                    ''', (trader_id, user_id))
                    ea_row = cur.fetchone()

                # 2. 否则按全局 connected + default 查找
                if not ea_row:
                    cur.execute('''
                        SELECT ea.id, ea.provider, ea.metadata_json, ea.environment
                        FROM exchange_accounts ea
                        WHERE ea.user_id = %s
                        ORDER BY ea.is_connected DESC, ea.is_default DESC, ea.id ASC
                        LIMIT 1
                    ''', (user_id,))
                    ea_row = cur.fetchone()

                # 如果直接查不到，通过 trader_instances 关联查
                if not ea_row:
                    cur.execute("""
                        SELECT ea.id, ea.provider, ea.metadata_json, ea.environment
                        FROM trader_instances ti
                        JOIN exchange_accounts ea ON ea.id = ti.exchange_account_id
                        WHERE ti.user_id = %s AND ti.exchange_account_id IS NOT NULL
                        ORDER BY ti.status = 'RUNNING' DESC, ti.id ASC
                        LIMIT 1
                    """, (user_id,))
                    ea_row = cur.fetchone()
        finally:
            conn.close()

        if not ea_row:
            return None, "No exchange account configured. Please set up your Binance API keys."

        # 解析 metadata_json
        meta = ea_row["metadata_json"]
        if meta and isinstance(meta, str):
            import json as _json
            try:
                meta = _json.loads(meta)
            except Exception:
                meta = {}
        if not isinstance(meta, dict):
            meta = {}

        raw_key = meta.get("api_key", "")
        raw_secret = meta.get("api_secret", "")
        environment = ea_row.get("environment", "demo")
        is_testnet = environment in ("testnet", "demo")

        # 解密（如果已加密）
        from binance_client import decrypt_value
        api_key = raw_key
        api_secret = raw_secret
        passphrase = meta.get("passphrase", "")
        
        if raw_key and raw_key.startswith("gAAAA"):
            try:
                api_key = decrypt_value(raw_key)
            except Exception:
                api_key = ""
        if raw_secret and raw_secret.startswith("gAAAA"):
            try:
                api_secret = decrypt_value(raw_secret)
            except Exception:
                api_secret = ""
        if passphrase and passphrase.startswith("gAAAA"):
            try:
                passphrase = decrypt_value(passphrase)
            except Exception:
                passphrase = ""

        if not api_key or not api_secret:
            return None, "Exchange account API credentials are empty or decryption failed."

        provider = ea_row.get("provider", "binance")
        
        from exchange_factory import create_exchange_client
        client = create_exchange_client(
            provider=provider,
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            environment=environment
        )
        print(f"[TradingTools] Client created via exchange_accounts (provider={provider}, env={environment}) for user {user_id[:8]}")
        return client, None

    except Exception as e:
        print(f"[BinanceTrading] _get_trading_client fallback error: {e}")
        return None, f"Failed to initialize trading client: {str(e)}"


# ==========================================
# Configuration
# ==========================================

# Default leverage for new positions
DEFAULT_LEVERAGE = 10

# Fee rate (0.05% for market orders)
FEE_RATE = 0.0005

# Minimum order sizes for common pairs (in base currency)
MIN_ORDER_SIZES = {
    "BTCUSDT": 0.001,
    "ETHUSDT": 0.001,
    "SOLUSDT": 0.01,
    "BNBUSDT": 0.01,
    "XRPUSDT": 1,
    "DOGEUSDT": 1,
    "DEFAULT": 0.001
}

# Price decimal places for common pairs (Binance Futures Mainnet)
# Reference: https://www.binance.com/en/futures/trading-rules/perpetual
PRICE_PRECISION = {
    "BTCUSDT": 1,   # 价格精度: 0.1
    "ETHUSDT": 2,   # 价格精度: 0.01
    "SOLUSDT": 3,   # 价格精度: 0.001
    "BNBUSDT": 2,
    "XRPUSDT": 4,
    "DOGEUSDT": 5,
    "DEFAULT": 2
}

# Quantity decimal places for common pairs (Binance Futures Mainnet)
QTY_PRECISION = {
    "BTCUSDT": 3,   # 最小数量: 0.001
    "ETHUSDT": 3,   # 最小数量: 0.001
    "SOLUSDT": 1,   # 最小数量: 0.1
    "BNBUSDT": 2,
    "XRPUSDT": 1,
    "DOGEUSDT": 0,
    "DEFAULT": 3
}


def get_symbol_usdt(symbol: str) -> str:
    """Ensure symbol ends with USDT."""
    symbol = symbol.upper()
    if not symbol.endswith("USDT"):
        return f"{symbol}USDT"
    return symbol


def round_quantity(symbol: str, quantity: float) -> float:
    """Round quantity to appropriate precision for the symbol."""
    symbol = get_symbol_usdt(symbol)
    precision = QTY_PRECISION.get(symbol, QTY_PRECISION["DEFAULT"])
    return round(quantity, precision)


def round_price(symbol: str, price: float) -> float:
    """Round price to appropriate precision for the symbol."""
    symbol = get_symbol_usdt(symbol)
    precision = PRICE_PRECISION.get(symbol, PRICE_PRECISION["DEFAULT"])
    return round(price, precision)


def get_min_order_size(symbol: str) -> float:
    """Get minimum order size for a symbol."""
    symbol = get_symbol_usdt(symbol)
    return MIN_ORDER_SIZES.get(symbol, MIN_ORDER_SIZES["DEFAULT"])


# ==========================================
# Binance Trading Functions
# ==========================================

def binance_get_usdt_balance(user_id: str = None) -> dict:
    """Get USDT balance for user."""
    user_id = _get_effective_user_id(user_id)
    client, err = _get_trading_client(user_id, require_trading_enabled=False)
    if err:
        return {"error": err}
    
    try:
        # returns dict with wallet_balance, available_balance, etc.
        balance_info = client.get_usdt_balance()
        if "error" in balance_info:
            return balance_info
            
        return {
            "balance": balance_info.get("wallet_balance", 0),
            "available_balance": balance_info.get("available_balance", 0),
            "margin_balance": balance_info.get("margin_balance", 0)
        }
    except Exception as e:
        return {"error": str(e)}


def binance_open_position(
    symbol: str,
    direction: str,
    margin: float,
    leverage: int = DEFAULT_LEVERAGE,
    stop_loss: float = None,
    take_profit: float = None,
    order_type: str = "MARKET",
    price: float = None,
    user_id: str = None
) -> dict:
    """
    在 Binance Futures 开仓。
    
    使用方法:
        open_position(symbol="BTC", direction="LONG", margin=100, leverage=10, stop_loss=89000)
        open_position(symbol="BTC", direction="LONG", margin=100, order_type="LIMIT", price=85000)
    
    Args:
        symbol: 交易对 (BTC, ETH, SOL 或 BTCUSDT)
        direction: 方向 LONG(做多) 或 SHORT(做空)
        margin: 保证金金额 (USDT)
        leverage: 杠杆倍数 (默认10倍，最高125倍)
        stop_loss: 止损价格 (可选，仅限 MARKET 单生效)
        take_profit: 止盈价格 (可选，仅限 MARKET 单生效)
        order_type: 订单类型 "MARKET" 或 "LIMIT" (默认 "MARKET")
        price: 限价单价格 (当 order_type="LIMIT" 时必填)
        user_id: 用户ID (可选，自动从上下文获取)
    
    Returns:
        dict with position details or error
    
    Example:
        open_position("BTC", "LONG", margin=500, leverage=10, stop_loss=88000, take_profit=95000)
    """
    # Get user_id from context if not provided
    user_id = _get_effective_user_id(user_id)
    
    # Validate inputs
    symbol = get_symbol_usdt(symbol)
    direction = direction.upper()
    order_type = order_type.upper()
    
    if direction not in ["LONG", "SHORT"]:
        return {"error": "Direction must be LONG or SHORT"}
    
    if margin <= 0:
        return {"error": "Margin must be positive"}
    
    if leverage < 1 or leverage > 125:
        return {"error": "Leverage must be between 1 and 125"}
        
    if order_type == "LIMIT" and (price is None or price <= 0):
        return {"error": "Price must be provided for LIMIT orders"}
    
    # Get trading client (supports both user_binance_keys and exchange_accounts)
    client, err = _get_trading_client(user_id)
    if err:
        return {"error": err}
    
    try:
        # Set leverage
        leverage_result = client.set_leverage(symbol, leverage)
        if "error" in leverage_result:
            # Ignore "No need to change leverage" error
            if "No need to change" not in str(leverage_result.get("error", "")):
                print(f"[BinanceTrading] Leverage warning: {leverage_result}")
        
        # Get current price (for quantity calculation if Market, or reference if Limit)
        price_info = client.get_mark_price(symbol)
        if "error" in price_info:
            return {"error": f"Failed to get price: {price_info['error']}"}
        
        current_price = float(price_info.get("markPrice", 0))
        if current_price <= 0:
            return {"error": f"Invalid price for {symbol}"}
        
        # Calculate quantity
        # For Limit orders, we use the specific limit price to calculate quantity
        # For Market orders, we use current mark price
        calc_price = price if order_type == "LIMIT" else current_price
        
        notional_value = margin * leverage
        quantity = notional_value / calc_price
        quantity = round_quantity(symbol, quantity)
        
        # [SAFETY CHECK] Min Notional Value
        if notional_value < 6.0:
            return {"error": f"Calculated order value {notional_value:.2f} is too small. Binance requires Min Notional > 5.0 (Safe > 6.0)."}
        
        # Check Position Mode (One-Way or Hedge)
        try:
            mode_resp = client.get_position_mode()
            is_hedge_mode = mode_resp.get("dualSidePosition", False) if isinstance(mode_resp, dict) else False
        except Exception as e:
            print(f"[BinanceTrading] Verify position mode failed: {e}")
            is_hedge_mode = False # Assume One-Way if fail
            
        # Determine side & positionSide
        if is_hedge_mode:
            # Hedge Mode: LONG -> Buy Long; SHORT -> Sell Short
            if direction == "LONG":
                side = "BUY"
                position_side = "LONG"
            else:
                side = "SELL"
                position_side = "SHORT"
            # Close side for SL/TP (if needed)
            close_side = "SELL" if direction == "LONG" else "BUY"
        else:
            # One-Way Mode: LONG -> Buy; SHORT -> Sell; positionSide="BOTH"
            side = "BUY" if direction == "LONG" else "SELL"
            position_side = "BOTH"
            close_side = "SELL" if direction == "LONG" else "BUY"
        
        # Build main order (MARKET or LIMIT)
        main_order = {
            "symbol": symbol,
            "side": side,
            "positionSide": position_side,
            "quantity": str(quantity)
        }
        
        if order_type == "LIMIT":
            price = round_price(symbol, price)
            main_order["type"] = "LIMIT"
            main_order["timeInForce"] = "GTC"
            main_order["price"] = str(price)
        else:
            main_order["type"] = "MARKET"
        
        # 1. 先下主订单
        print(f"[BinanceTrading] Placing main {order_type} order: {main_order}")
        batch_result = client.place_batch_orders([main_order])
        
        if isinstance(batch_result, dict) and "error" in batch_result:
            return {"error": f"main order failed: {batch_result['error']}"}
        
        if not isinstance(batch_result, list) or len(batch_result) == 0:
            return {"error": f"Unexpected batch result: {batch_result}"}
        
        main_result = batch_result[0]
        if "error" in main_result or "code" in main_result:
            return {"error": f"Main order failed: {main_result}"}
        
        order_id = main_result.get("orderId")
        avg_price = float(main_result.get("avgPrice", 0) or 0)
        executed_qty = float(main_result.get("executedQty", 0) or 0)
        
        # 2. 下止损单 (使用 Algo Order API)
        sl_order_id = None
        if stop_loss and order_type == "MARKET":
            stop_loss = round_price(symbol, stop_loss)
            try:
                sl_result = client.place_stop_market_order(
                    symbol=symbol,
                    side=close_side,
                    quantity=executed_qty if executed_qty > 0 else quantity,
                    stop_price=stop_loss,
                    reduce_only=not is_hedge_mode,
                    position_side=position_side if is_hedge_mode else None
                )
                if isinstance(sl_result, dict) and "algoId" in sl_result:
                    sl_order_id = sl_result.get("algoId")
                elif isinstance(sl_result, dict) and "orderId" in sl_result:
                    sl_order_id = sl_result.get("orderId")
                else:
                    print(f"[BinanceTrading] SL order result: {sl_result}")
            except Exception as e:
                print(f"[BinanceTrading] Failed to place SL: {e}")
        
        # 3. 下止盈单 (使用 Algo Order API)
        tp_order_id = None
        if take_profit and order_type == "MARKET":
            take_profit = round_price(symbol, take_profit)
            try:
                tp_result = client.place_take_profit_market_order(
                    symbol=symbol,
                    side=close_side,
                    quantity=executed_qty if executed_qty > 0 else quantity,
                    stop_price=take_profit,
                    reduce_only=not is_hedge_mode,
                    position_side=position_side if is_hedge_mode else None
                )
                if isinstance(tp_result, dict) and "algoId" in tp_result:
                    tp_order_id = tp_result.get("algoId")
                elif isinstance(tp_result, dict) and "orderId" in tp_result:
                    tp_order_id = tp_result.get("orderId")
                else:
                    print(f"[BinanceTrading] TP order result: {tp_result}")
            except Exception as e:
                print(f"[BinanceTrading] Failed to place TP: {e}")
        
        # Calculate fee (estimate)
        fee = notional_value * FEE_RATE
        
        # Construct success message
        msg = f"Opened {direction} position on {symbol}"
        if order_type == "LIMIT":
            msg = f"Placed LIMIT {direction} order on {symbol} at ${price}"
            if stop_loss or take_profit:
                msg += ". (Warning: SL/TP NOT set for Limit Order)"
        
        return {
            "success": True,
            "order_id": order_id,
            "symbol": symbol,
            "direction": direction,
            "margin": margin,
            "leverage": leverage,
            "entry_price": avg_price if avg_price > 0 else (price if order_type == "LIMIT" else current_price),
            "quantity": executed_qty if executed_qty > 0 else quantity,
            "stop_loss": stop_loss if order_type == "MARKET" else None,
            "take_profit": take_profit if order_type == "MARKET" else None,
            "sl_order_id": sl_order_id,
            "tp_order_id": tp_order_id,
            "fee": fee,
            "order_type": order_type,
            "message": msg
        }
        
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def binance_close_position(
    symbol: str,
    close_percent: float = 100,
    reason: str = "manual",
    user_id: str = None
) -> dict:
    """
    在 Binance Futures 平仓。
    
    使用方法:
        close_position(symbol="BTC")  # 全部平仓
        close_position(symbol="BTC", close_percent=50)  # 平仓50%
    
    Args:
        symbol: 交易对 (BTC, ETH, SOL 或 BTCUSDT)
        close_percent: 平仓比例 (1-100，默认100全部平仓)
        reason: 平仓原因 (manual/stop_loss/take_profit)
        user_id: 用户ID (可选，自动从上下文获取)
    
    Returns:
        dict with close details or error
    
    Example:
        close_position("BTC")  # 全部平仓
        close_position("BTC", close_percent=50, reason="take_profit")  # 止盈平50%
    """
    # Get user_id from context if not provided
    user_id = _get_effective_user_id(user_id)
    
    symbol = get_symbol_usdt(symbol)
    
    if close_percent <= 0 or close_percent > 100:
        return {"error": "close_percent must be between 1 and 100"}
    
    # Get trading client (supports both user_binance_keys and exchange_accounts)
    client, err = _get_trading_client(user_id)
    if err:
        return {"error": err}
    
    try:
        # Get current positions
        positions = client.get_positions()
        if "error" in positions:
            return {"error": f"Failed to get positions: {positions['error']}"}
        
        # Find position for this symbol
        position = None
        for pos in positions:
            if pos.get("symbol") == symbol:
                position = pos
                break
        
        if not position:
            return {"error": f"No open position found for {symbol}"}
        
        direction = position.get("direction")
        quantity = position.get("quantity", 0)
        entry_price = position.get("entry_price", 0)
        
        # Calculate quantity to close
        close_qty = quantity * (close_percent / 100)
        close_qty = round_quantity(symbol, close_qty)
        
        # Check Position Mode (One-Way or Hedge)
        try:
            mode_resp = client.get_position_mode()
            is_hedge_mode = mode_resp.get("dualSidePosition", False) if isinstance(mode_resp, dict) else False
        except Exception as e:
            print(f"[BinanceTrading] Check position mode failed: {e}")
            is_hedge_mode = False
        
        # Determine side and positionSide based on mode
        if is_hedge_mode:
            # Hedge Mode: use positionSide, NOT reduceOnly
            side = "SELL" if direction == "LONG" else "BUY"
            position_side = direction  # LONG or SHORT
            use_reduce_only = False
        else:
            # One-Way Mode: use reduceOnly, NOT positionSide
            side = "SELL" if direction == "LONG" else "BUY"
            position_side = None
            use_reduce_only = True
        
        # Place market order to close
        order_result = client.place_market_order(
            symbol, side, close_qty, 
            reduce_only=use_reduce_only,
            position_side=position_side
        )
        
        if "error" in order_result:
            return {"error": f"Failed to close position: {order_result['error']}"}
        
        avg_price = float(order_result.get("avgPrice", 0))
        executed_qty = float(order_result.get("executedQty", close_qty))
        
        # Calculate realized PnL
        if direction == "LONG":
            pnl = executed_qty * (avg_price - entry_price)
        else:
            pnl = executed_qty * (entry_price - avg_price)
        
        # Subtract fee
        fee = executed_qty * avg_price * FEE_RATE
        realized_pnl = pnl - fee
        
        # Cancel associated SL/TP orders if no remaining position
        # 不再只检查 close_percent == 100，而是平仓后主动检测该 symbol 是否还有剩余仓位
        try:
            if close_percent == 100:
                # 全平仓 → 直接清理所有挂单
                cancel_result = client.cancel_all_orders_and_algo(symbol)
                print(f"[BinanceTrading] Cancelled all orders on full close: {cancel_result}")
            else:
                # 部分平仓 → 检查是否还有剩余仓位，没有则清理
                remaining_positions = client.get_positions()
                has_remaining = False
                if isinstance(remaining_positions, list):
                    for rp in remaining_positions:
                        if rp.get("symbol") == symbol:
                            has_remaining = True
                            break
                
                if not has_remaining:
                    cancel_result = client.cancel_all_orders_and_algo(symbol)
                    print(f"[BinanceTrading] No remaining position for {symbol} after partial close, cleaned up orphan orders: {cancel_result}")
        except Exception as e:
            print(f"[BinanceTrading] Failed to cancel orders after close: {e}")
        
        return {
            "success": True,
            "symbol": symbol,
            "direction": direction,
            "closed_percent": close_percent,
            "closed_quantity": executed_qty,
            "entry_price": entry_price,
            "close_price": avg_price,
            "realized_pnl": round(realized_pnl, 2),
            "fee": round(fee, 2),
            "reason": reason,
            "message": f"Closed {close_percent}% of {direction} position on {symbol}"
        }
        
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def binance_get_positions_summary(user_id: str = None) -> dict:
    """
    获取 Binance 账户余额和持仓汇总。
    
    使用方法:
        get_positions_summary()  # 查看当前持仓和余额
    
    Returns:
        dict with:
        - available_balance: 可用余额
        - margin_in_use: 已用保证金
        - unrealized_pnl: 未实现盈亏
        - equity: 总权益
        - open_positions: 持仓列表
    """
    # Get user_id from context if not provided
    user_id = _get_effective_user_id(user_id)
    
    # Debug: print user_id for troubleshooting
    print(f"[BinanceTools] binance_get_positions_summary called with user_id: {user_id}")
    
    # Validate user_id format (should be a UUID or valid user identifier)
    # "user" is an invalid placeholder that means context was not properly set
    if user_id == "user" or not user_id or len(user_id) < 10:
        print(f"[BinanceTools] Invalid user_id detected: '{user_id}' - context not properly set by middleware")
        return {
            "error": "用户身份验证失败，请重新登录后再试",
            "is_configured": False,
            "debug_info": f"received user_id: {user_id}"
        }
    
    # Get trading client (supports both user_binance_keys and exchange_accounts)
    client, err = _get_trading_client(user_id, require_trading_enabled=False)
    if err:
        print(f"[BinanceTools] Client creation failed for user: {user_id[:8]}: {err}")
        return {
            "error": err,
            "is_configured": False,
            "debug_user_id": user_id
        }
    
    status = get_user_trading_status(user_id)
    
    try:
        # Get balance - 直接使用 API 返回的总金额
        balance = client.get_usdt_balance()
        if "error" in balance:
            return {"error": f"Failed to get balance: {balance['error']}"}
        
        # 使用 API 直接返回的金额，不自己计算
        wallet_balance = balance.get("wallet_balance", 0)      # 账户总余额
        margin_balance = balance.get("margin_balance", 0)      # 保证金余额 (含未实现盈亏)
        available_balance = balance.get("available_balance", 0) # 可用余额
        unrealized_pnl = balance.get("unrealized_pnl", 0)      # 总未实现盈亏
        
        # Get positions
        positions = client.get_positions()
        if isinstance(positions, dict) and "error" in positions:
            return {"error": f"Failed to get positions: {positions['error']}"}
        
        open_positions = []
        total_margin = 0
        
        for pos in positions:
            entry_price = pos.get("entry_price", 0)
            mark_price = pos.get("mark_price", 0)
            quantity = pos.get("quantity", 0)
            direction = pos.get("direction")
            leverage = pos.get("leverage", 10)
            
            # Calculate margin (notional / leverage)
            notional = quantity * entry_price
            margin = notional / leverage if leverage > 0 else notional
            total_margin += margin
            
            # Calculate ROI
            pos_pnl = pos.get("unrealized_pnl", 0)
            roi = (pos_pnl / margin * 100) if margin > 0 else 0
            
            open_positions.append({
                "symbol": pos.get("symbol"),
                "direction": direction,
                "margin": round(margin, 2),
                "leverage": leverage,
                "entry_price": entry_price,
                "current_price": mark_price,
                "quantity": quantity,
                "unrealized_pnl": round(pos_pnl, 2),
                "roi_percent": round(roi, 2),
                "liquidation_price": pos.get("liquidation_price", 0)
            })
        
        return {
            # 余额信息 - 直接使用 API 返回的值
            "wallet_balance": round(wallet_balance, 2),        # 账户总余额
            "margin_balance": round(margin_balance, 2),        # 保证金余额
            "available_balance": round(available_balance, 2),  # 可用余额
            "unrealized_pnl": round(unrealized_pnl, 2),        # 未实现盈亏
            "equity": round(margin_balance, 2),                # 总权益 = margin_balance
            # 持仓信息
            "margin_in_use": round(total_margin, 2),
            "open_positions": open_positions,
            "position_count": len(open_positions),
            "is_trading_enabled": status.get("is_trading_enabled", False),
            "balance_breakdown": balance.get("assets", [])
        }
        
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def binance_get_current_price(symbol: str, user_id: str = None) -> float:
    """
    Get current price from Binance Futures.
    
    Args:
        symbol: Coin symbol
        user_id: Optional user ID (uses public endpoint if not provided)
    
    Returns:
        Current mark price or 0 if error
    """
    symbol = get_symbol_usdt(symbol)
    
    # Try user client first if available
    if user_id:
        client = get_user_binance_client(user_id)
        if client:
            try:
                result = client.get_mark_price(symbol)
                if "error" not in result:
                    return float(result.get("markPrice", 0))
            except:
                pass
    
    # Fallback 1: Binance Public API
    import requests
    try:
        url = f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        # 增加超时时间到 10s -> 缩短为3s以快速failover
        resp = requests.get(url, headers=headers, timeout=3)
        
        if resp.status_code != 200:
             print(f"[BinanceTrading] Price fetch failed for {symbol}: Status {resp.status_code}")
        else:
            data = resp.json()
            return float(data.get("markPrice", 0))
            
    except Exception as e:
        print(f"[BinanceTrading] Binance API failed for {symbol}: {str(e)[:100]}")
    
    # Fallback 2: CoinGecko API (最后一道防线)
    try:
        # 映射 symbol: BTCUSDT -> bitcoin, ETHUSDT -> ethereum
        cg_id = "bitcoin" if "BTC" in symbol else "ethereum" if "ETH" in symbol else "solana" if "SOL" in symbol else None
        
        if cg_id:
            cg_url = f"https://api.coingecko.com/api/v3/simple/price?ids={cg_id}&vs_currencies=usd"
            cg_headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json"
            }
            resp = requests.get(cg_url, headers=cg_headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                price = data.get(cg_id, {}).get("usd", 0)
                if price > 0:
                    print(f"[BinanceTrading] Used CoinGecko fallback for {symbol}: {price}")
                    return float(price)
    except Exception as e:
        print(f"[BinanceTrading] CoinGecko fallback failed: {e}")

    return 0


def binance_update_stop_loss(
    symbol: str,
    new_stop_loss: float,
    user_id: str = None
) -> dict:
    """
    更新持仓的止损价格。
    
    使用方法:
        update_stop_loss(symbol="BTC", new_stop_loss=90000)
    
    Args:
        symbol: 交易对 (BTC, ETH, SOL 或 BTCUSDT)
        new_stop_loss: 新止损价格
        user_id: 用户ID (可选，自动从上下文获取)
    
    Returns:
        dict with update status
    
    Example:
        update_stop_loss("BTC", 90000)  # 将BTC止损移到90000
    """
    # Get user_id from context if not provided
    user_id = _get_effective_user_id(user_id)
    
    symbol = get_symbol_usdt(symbol)
    
    client, err = _get_trading_client(user_id)
    if err:
        return {"error": err}
    
    try:
        # Get current position
        positions = client.get_positions()
        if "error" in positions:
            return {"error": f"Failed to get positions: {positions['error']}"}
        
        position = None
        for pos in positions:
            if pos.get("symbol") == symbol:
                position = pos
                break
        
        if not position:
            return {"error": f"No open position found for {symbol}"}
        
        direction = position.get("direction")
        quantity = position.get("quantity", 0)
        
        # Check Position Mode (One-Way or Hedge)
        try:
            mode_resp = client.get_position_mode()
            is_hedge_mode = mode_resp.get("dualSidePosition", False) if isinstance(mode_resp, dict) else False
        except Exception as e:
            print(f"[BinanceTrading] Check position mode failed: {e}")
            is_hedge_mode = False
        
        # 1. 只取消现有的 SL 类订单（保留 TP 订单）
        sl_types = {"STOP_MARKET", "STOP", "TRAILING_STOP_MARKET"}
        cancelled_count = 0
        
        # 取消普通 SL 挂单
        try:
            normal_orders = client.get_open_orders(symbol)
            if isinstance(normal_orders, list):
                for order in normal_orders:
                    if order.get("type", "") in sl_types:
                        order_id = order.get("orderId")
                        if order_id:
                            try:
                                client.cancel_order(symbol, str(order_id))
                                cancelled_count += 1
                            except Exception as e:
                                print(f"[Trading] Failed to cancel SL order {order_id}: {e}")
        except Exception as e:
            print(f"[Trading] Failed to get orders for SL cancel: {e}")
        
        # 取消 Algo SL 挂单（统一接口，适用于所有交易所）
        try:
            algo_orders = client.get_open_algo_orders()
            if isinstance(algo_orders, list):
                for order in algo_orders:
                    order_type = order.get("algoType") or order.get("type", "")
                    if order.get("symbol") == symbol and order_type in sl_types:
                        algo_id = order.get("algoId") or order.get("orderId")
                        if algo_id:
                            try:
                                client.cancel_algo_order(symbol, str(algo_id))
                                cancelled_count += 1
                            except Exception as e:
                                print(f"[Trading] Failed to cancel algo SL {algo_id}: {e}")
        except Exception:
            pass
        
        print(f"[Trading] Cancelled {cancelled_count} existing SL orders for {symbol}")
        
        # Place new SL order
        new_stop_loss = round_price(symbol, new_stop_loss)
        sl_side = "SELL" if direction == "LONG" else "BUY"
        
        # Determine positionSide and reduceOnly based on mode
        # Hedge Mode: use positionSide, NOT reduceOnly
        # One-Way Mode: use reduceOnly, NOT positionSide
        position_side = direction if is_hedge_mode else None
        use_reduce_only = not is_hedge_mode
        
        sl_result = client.place_stop_market_order(
            symbol, sl_side, quantity, new_stop_loss,
            reduce_only=use_reduce_only,
            position_side=position_side
        )
        
        if "error" in sl_result:
            return {"error": f"Failed to place SL: {sl_result['error']}"}
        
        return {
            "success": True,
            "symbol": symbol,
            "new_stop_loss": new_stop_loss,
            "sl_order_id": sl_result.get("orderId")
        }
        
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def binance_update_take_profit(
    symbol: str,
    new_take_profit: float,
    user_id: str = None
) -> dict:
    """
    更新持仓的止盈价格（只替换现有的 TP 订单，不影响 SL 订单）。
    
    使用方法:
        update_take_profit(symbol="BTC", new_take_profit=100000)
    
    Args:
        symbol: 交易对 (BTC, ETH, SOL 或 BTCUSDT)
        new_take_profit: 新止盈价格
        user_id: 用户ID (可选，自动从上下文获取)
    
    Returns:
        dict with update status
    
    Example:
        update_take_profit("BTC", 100000)  # 将BTC止盈移到100000
    """
    user_id = _get_effective_user_id(user_id)
    symbol = get_symbol_usdt(symbol)
    
    client, err = _get_trading_client(user_id)
    if err:
        return {"error": err}
    
    try:
        # Get current position
        positions = client.get_positions()
        if "error" in positions:
            return {"error": f"Failed to get positions: {positions['error']}"}
        
        position = None
        for pos in positions:
            if pos.get("symbol") == symbol:
                position = pos
                break
        
        if not position:
            return {"error": f"No open position found for {symbol}"}
        
        direction = position.get("direction")
        quantity = position.get("quantity", 0)
        
        # Check Position Mode
        try:
            mode_resp = client.get_position_mode()
            is_hedge_mode = mode_resp.get("dualSidePosition", False) if isinstance(mode_resp, dict) else False
        except Exception:
            is_hedge_mode = False
        
        # 1. 只取消现有的 TP 类订单（保留 SL 订单）
        tp_types = {"TAKE_PROFIT_MARKET", "TAKE_PROFIT"}
        cancelled_count = 0
        
        # 取消普通 TP 挂单
        try:
            normal_orders = client.get_open_orders(symbol)
            if isinstance(normal_orders, list):
                for order in normal_orders:
                    if order.get("type", "") in tp_types:
                        order_id = order.get("orderId")
                        if order_id:
                            try:
                                client.cancel_order(symbol, str(order_id))
                                cancelled_count += 1
                            except Exception as e:
                                print(f"[Trading] Failed to cancel TP order {order_id}: {e}")
        except Exception as e:
            print(f"[Trading] Failed to get orders for TP cancel: {e}")
        
        # 取消 Algo TP 挂单（统一接口，适用于所有交易所）
        try:
            algo_orders = client.get_open_algo_orders()
            if isinstance(algo_orders, list):
                for order in algo_orders:
                    order_type = order.get("algoType") or order.get("type", "")
                    if order.get("symbol") == symbol and order_type in tp_types:
                        algo_id = order.get("algoId") or order.get("orderId")
                        if algo_id:
                            try:
                                client.cancel_algo_order(symbol, str(algo_id))
                                cancelled_count += 1
                            except Exception as e:
                                print(f"[Trading] Failed to cancel algo TP {algo_id}: {e}")
        except Exception:
            pass
        
        print(f"[Trading] Cancelled {cancelled_count} existing TP orders for {symbol}")
        
        # 2. Place new TP order
        new_take_profit = round_price(symbol, new_take_profit)
        tp_side = "SELL" if direction == "LONG" else "BUY"
        position_side = direction if is_hedge_mode else None
        use_reduce_only = not is_hedge_mode
        
        tp_result = client.place_take_profit_market_order(
            symbol=symbol,
            side=tp_side,
            quantity=quantity,
            stop_price=new_take_profit,
            reduce_only=use_reduce_only,
            position_side=position_side
        )
        
        if isinstance(tp_result, dict) and "error" in tp_result:
            return {"error": f"Failed to place TP: {tp_result['error']}"}
        
        tp_order_id = tp_result.get("algoId") or tp_result.get("orderId")
        
        return {
            "success": True,
            "symbol": symbol,
            "new_take_profit": new_take_profit,
            "tp_order_id": tp_order_id,
            "cancelled_old_tp_count": cancelled_count,
        }
        
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def binance_get_open_orders(user_id: str, symbol: str = None) -> dict:
    """
    Get open orders from Binance.
    
    Args:
        user_id: User ID
        symbol: Optional symbol filter
    
    Returns:
        dict with open orders
    """
    client = get_user_binance_client(user_id)
    if not client:
        return {"error": "Failed to create Binance client"}
    
    try:
        if symbol:
            symbol = get_symbol_usdt(symbol)
        
        orders = client.get_open_orders(symbol)
        
        if isinstance(orders, dict) and "error" in orders:
            return {"error": f"Failed to get orders: {orders['error']}"}
        
        formatted_orders = []
        for order in orders:
            formatted_orders.append({
                "order_id": order.get("orderId"),
                "symbol": order.get("symbol"),
                "type": order.get("type"),
                "side": order.get("side"),
                "quantity": float(order.get("origQty", 0)),
                "price": float(order.get("price", 0)),
                "stop_price": float(order.get("stopPrice", 0)),
                "status": order.get("status"),
                "time": order.get("time")
            })
        
        return {
            "success": True,
            "orders": formatted_orders,
            "count": len(formatted_orders)
        }
        
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


# ==========================================
# Phase 2: 新增交易增强功能
# ==========================================

def binance_modify_order(
    symbol: str,
    order_id: int,
    quantity: float,
    price: float,
    user_id: str = None
) -> dict:
    """
    修改已挂的限价订单价格和数量。
    
    注意：只能修改限价单，市价单无法修改。
    
    使用方法:
        modify_order(symbol="BTC", order_id=123456, quantity=0.01, price=95000)
    
    Args:
        symbol: 交易对 (BTC, ETH, SOL 或 BTCUSDT)
        order_id: 要修改的订单 ID
        quantity: 新的数量
        price: 新的价格
        user_id: 用户ID (可选，自动从上下文获取)
    
    Returns:
        dict with modified order info or error
    """
    user_id = _get_effective_user_id(user_id)
    symbol = get_symbol_usdt(symbol)
    
    # Check user status
    client, err = _get_trading_client(user_id, require_trading_enabled=True)
    if err:
        return {"error": err}
    
    try:
        # Get order details to determine side
        orders = client.get_open_orders(symbol)
        if isinstance(orders, dict) and "error" in orders:
            return {"error": f"Failed to get orders: {orders['error']}"}
        
        # Find the order
        target_order = None
        for order in orders:
            if order.get("orderId") == order_id:
                target_order = order
                break
        
        if not target_order:
            return {"error": f"Order {order_id} not found or already filled/cancelled"}
        
        side = target_order.get("side", "BUY")
        
        # Round values
        quantity = round_quantity(symbol, quantity)
        price = round_price(symbol, price)
        
        result = client.modify_order(symbol, order_id, side, quantity, price)
        
        if isinstance(result, dict) and "error" in result:
            return {"error": f"Failed to modify order: {result['error']}"}
        
        return {
            "success": True,
            "order_id": result.get("orderId"),
            "symbol": symbol,
            "side": result.get("side"),
            "new_quantity": float(result.get("origQty", quantity)),
            "new_price": float(result.get("price", price)),
            "status": result.get("status"),
            "message": f"Order {order_id} modified successfully"
        }
        
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def binance_get_income_history(
    symbol: str = None,
    income_type: str = None,
    limit: int = 50,
    user_id: str = None
) -> dict:
    """
    获取收益历史记录。
    
    使用方法:
        get_income_history()  # 全部收益记录
        get_income_history(income_type="FUNDING_FEE")  # 资金费率记录
        get_income_history(symbol="BTC", income_type="REALIZED_PNL")  # BTC 已实现盈亏
    
    Args:
        symbol: 交易对 (可选，如 "BTC" 或 "BTCUSDT")
        income_type: 收益类型 (可选)
            - "REALIZED_PNL": 已实现盈亏
            - "FUNDING_FEE": 资金费率
            - "COMMISSION": 手续费
            - "TRANSFER": 转账
        limit: 返回数量 (默认50，最大1000)
        user_id: 用户ID (可选)
    
    Returns:
        dict with income history list
    """
    user_id = _get_effective_user_id(user_id)
    
    if symbol:
        symbol = get_symbol_usdt(symbol)
    
    client, err = _get_trading_client(user_id, require_trading_enabled=False)
    if err:
        return {"error": err}
    
    try:
        result = client.get_income_history(
            symbol=symbol,
            income_type=income_type,
            limit=limit
        )
        
        if isinstance(result, dict) and "error" in result:
            return {"error": f"Failed to get income history: {result['error']}"}
        
        if not isinstance(result, list):
            return {"error": "Unexpected response format"}
        
        # Format and summarize
        formatted = []
        total_pnl = 0.0
        total_funding = 0.0
        total_commission = 0.0
        
        for record in result:
            income = float(record.get("income", 0))
            record_type = record.get("incomeType", "")
            
            if record_type == "REALIZED_PNL":
                total_pnl += income
            elif record_type == "FUNDING_FEE":
                total_funding += income
            elif record_type == "COMMISSION":
                total_commission += income
            
            formatted.append({
                "symbol": record.get("symbol"),
                "type": record_type,
                "amount": income,
                "asset": record.get("asset"),
                "time": record.get("time"),
                "info": record.get("info", "")
            })
        
        return {
            "success": True,
            "records": formatted,
            "count": len(formatted),
            "summary": {
                "total_realized_pnl": round(total_pnl, 4),
                "total_funding_fee": round(total_funding, 4),
                "total_commission": round(total_commission, 4)
            }
        }
        
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def binance_get_funding_rate(
    symbol: str,
    limit: int = 10,
    user_id: str = None
) -> dict:
    """
    获取资金费率历史。
    
    使用方法:
        get_funding_rate("BTC")  # 获取 BTC 最近10次资金费率
        get_funding_rate("ETH", limit=50)  # 获取 ETH 最近50次
    
    Args:
        symbol: 交易对 (如 "BTC" 或 "BTCUSDT")
        limit: 返回数量 (默认10)
        user_id: 用户ID (可选，用于正式网访问)
    
    Returns:
        dict with funding rate history
    """
    symbol = get_symbol_usdt(symbol)
    
    # Try user client first, fallback to public API
    client = None
    if user_id:
        user_id = _get_effective_user_id(user_id)
        client, _ = _get_trading_client(user_id, require_trading_enabled=False)
    
    try:
        if client:
            result = client.get_funding_rate(symbol, limit)
        else:
            # Public API fallback
            import requests
            url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}&limit={limit}"
            resp = requests.get(url, timeout=10)
            result = resp.json()
        
        if isinstance(result, dict) and "error" in result:
            return {"error": f"Failed to get funding rate: {result.get('error')}"}
        
        if not isinstance(result, list):
            return {"error": "Unexpected response format"}
        
        # Format
        formatted = []
        for record in result:
            rate = float(record.get("fundingRate", 0))
            formatted.append({
                "symbol": record.get("symbol"),
                "funding_rate": rate,
                "funding_rate_percent": round(rate * 100, 4),
                "funding_time": record.get("fundingTime"),
                "mark_price": float(record.get("markPrice", 0))
            })
        
        # Calculate average and current
        avg_rate = sum(r["funding_rate"] for r in formatted) / len(formatted) if formatted else 0
        current_rate = formatted[0]["funding_rate"] if formatted else 0
        
        return {
            "success": True,
            "symbol": symbol,
            "rates": formatted,
            "current_rate": current_rate,
            "current_rate_percent": round(current_rate * 100, 4),
            "average_rate": round(avg_rate, 6),
            "average_rate_percent": round(avg_rate * 100, 4)
        }
        
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


# ==========================================
# Phase 3: 风控增强功能
# ==========================================

def binance_get_adl_risk(user_id: str = None) -> dict:
    """
    获取所有持仓的 ADL (自动减仓) 风险等级。
    
    ADL 等级说明：
    - 0: 无持仓
    - 1-2: 低风险 (安全)
    - 3: 中风险 (需注意)
    - 4-5: 高风险 (可能被减仓)
    
    使用方法:
        get_adl_risk()  # 获取所有持仓的 ADL 风险
    
    Returns:
        dict with ADL risk info for all positions
    """
    user_id = _get_effective_user_id(user_id)
    
    client, err = _get_trading_client(user_id, require_trading_enabled=False)
    if err:
        return {"error": err}
    
    try:
        result = client.get_adl_quantile()
        
        if isinstance(result, dict) and "error" in result:
            return {"error": f"Failed to get ADL info: {result['error']}"}
        
        if not isinstance(result, list):
            result = [result] if result else []
        
        # Format and add risk level descriptions
        formatted = []
        high_risk_positions = []
        
        for item in result:
            symbol = item.get("symbol", "")
            adl_info = item.get("adlQuantile", {})
            
            # ADL 有时按持仓方向分开
            long_adl = adl_info.get("LONG", 0) if isinstance(adl_info, dict) else adl_info
            short_adl = adl_info.get("SHORT", 0) if isinstance(adl_info, dict) else 0
            both_adl = adl_info.get("BOTH", 0) if isinstance(adl_info, dict) else 0
            
            max_adl = max(long_adl, short_adl, both_adl)
            
            if max_adl == 0:
                continue  # Skip positions with no ADL info
            
            risk_level = "低风险" if max_adl <= 2 else "中风险" if max_adl == 3 else "高风险"
            
            position_info = {
                "symbol": symbol,
                "adl_level": max_adl,
                "risk_level": risk_level,
                "long_adl": long_adl,
                "short_adl": short_adl,
                "is_dangerous": max_adl >= 4
            }
            formatted.append(position_info)
            
            if max_adl >= 4:
                high_risk_positions.append(symbol)
        
        return {
            "success": True,
            "positions": formatted,
            "high_risk_count": len(high_risk_positions),
            "high_risk_symbols": high_risk_positions,
            "warning": f"⚠️ {len(high_risk_positions)} 个持仓处于高风险状态！" if high_risk_positions else None
        }
        
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def binance_get_force_orders(
    symbol: str = None,
    limit: int = 20,
    user_id: str = None
) -> dict:
    """
    获取强平订单历史。
    
    使用方法:
        get_force_orders()  # 获取所有强平历史
        get_force_orders(symbol="BTC")  # 获取 BTC 强平历史
    
    Args:
        symbol: 交易对 (可选)
        limit: 返回数量 (默认20)
        user_id: 用户ID
    
    Returns:
        dict with force order history
    """
    user_id = _get_effective_user_id(user_id)
    
    if symbol:
        symbol = get_symbol_usdt(symbol)
    
    client, err = _get_trading_client(user_id, require_trading_enabled=False)
    if err:
        return {"error": err}
    
    try:
        result = client.get_force_orders(symbol=symbol, limit=limit)
        
        if isinstance(result, dict) and "error" in result:
            return {"error": f"Failed to get force orders: {result['error']}"}
        
        if not isinstance(result, list):
            return {"success": True, "orders": [], "count": 0}
        
        # Format
        formatted = []
        total_loss = 0.0
        
        for order in result:
            pnl = float(order.get("realizedPnl", 0))
            total_loss += pnl
            
            formatted.append({
                "symbol": order.get("symbol"),
                "side": order.get("side"),
                "quantity": float(order.get("origQty", 0)),
                "price": float(order.get("price", 0)),
                "avg_price": float(order.get("avgPrice", 0)),
                "type": order.get("type"),
                "close_type": order.get("autoCloseType"),  # LIQUIDATION or ADL
                "realized_pnl": pnl,
                "time": order.get("time")
            })
        
        return {
            "success": True,
            "orders": formatted,
            "count": len(formatted),
            "total_loss": round(total_loss, 4)
        }
        
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def binance_get_leverage_info(
    symbol: str = None,
    user_id: str = None
) -> dict:
    """
    获取杠杆档位信息（显示不同仓位大小对应的最大杠杆）。
    
    使用方法:
        get_leverage_info("BTC")  # 获取 BTC 杠杆档位
    
    Args:
        symbol: 交易对 (如 "BTC" 或 "BTCUSDT")
        user_id: 用户ID
    
    Returns:
        dict with leverage bracket info
    """
    user_id = _get_effective_user_id(user_id)
    
    if symbol:
        symbol = get_symbol_usdt(symbol)
    
    client, err = _get_trading_client(user_id, require_trading_enabled=False)
    if err:
        return {"error": err}
    
    try:
        result = client.get_leverage_bracket(symbol)
        
        if isinstance(result, dict) and "error" in result:
            return {"error": f"Failed to get leverage info: {result['error']}"}
        
        if not isinstance(result, list):
            return {"error": "Unexpected response format"}
        
        # Format
        formatted = []
        for item in result:
            sym = item.get("symbol", "")
            brackets = item.get("brackets", [])
            
            bracket_info = []
            for b in brackets:
                bracket_info.append({
                    "bracket": b.get("bracket"),
                    "initial_leverage": b.get("initialLeverage"),
                    "notional_cap": b.get("notionalCap"),
                    "notional_floor": b.get("notionalFloor"),
                    "maint_margin_ratio": b.get("maintMarginRatio")
                })
            
            formatted.append({
                "symbol": sym,
                "brackets": bracket_info,
                "max_leverage": brackets[0].get("initialLeverage") if brackets else 0
            })
        
        # If single symbol requested, simplify output
        if symbol and len(formatted) == 1:
            return {
                "success": True,
                **formatted[0]
            }
        
        return {
            "success": True,
            "symbols": formatted
        }
        
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def binance_get_commission_rate(
    symbol: str,
    user_id: str = None
) -> dict:
    """
    获取用户的佣金费率。
    
    使用方法:
        get_commission_rate("BTC")  # 获取 BTC 交易的佣金费率
    
    Args:
        symbol: 交易对
        user_id: 用户ID
    
    Returns:
        dict with maker/taker commission rates
    """
    user_id = _get_effective_user_id(user_id)
    symbol = get_symbol_usdt(symbol)
    
    client, err = _get_trading_client(user_id, require_trading_enabled=False)
    if err:
        return {"error": err}
    
    try:
        result = client.get_commission_rate(symbol)
        
        if isinstance(result, dict) and "error" in result:
            return {"error": f"Failed to get commission rate: {result['error']}"}
        
        maker_rate = float(result.get("makerCommissionRate", 0))
        taker_rate = float(result.get("takerCommissionRate", 0))
        
        return {
            "success": True,
            "symbol": symbol,
            "maker_rate": maker_rate,
            "maker_rate_percent": round(maker_rate * 100, 4),
            "taker_rate": taker_rate,
            "taker_rate_percent": round(taker_rate * 100, 4)
        }
        
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


# ==========================================
# Phase 4: 高级订单类型
# ==========================================

def binance_place_trailing_stop(
    symbol: str,
    callback_rate: float,
    quantity: float = None,
    close_percent: float = 100,
    activation_price: float = None,
    user_id: str = None
) -> dict:
    """
    设置跟踪止损订单。
    
    跟踪止损会根据价格波动自动调整止损价格，
    在价格上涨时锁定利润，下跌超过回调比例时触发平仓。
    
    使用方法:
        place_trailing_stop("BTC", callback_rate=1.0)  # 1% 回调
        place_trailing_stop("ETH", callback_rate=0.5, activation_price=4000)
    
    Args:
        symbol: 交易对 (如 "BTC" 或 "BTCUSDT")
        callback_rate: 回调比例 (0.1-5，如 1.0 = 1%)
        quantity: 平仓数量 (可选，不传则使用 close_percent 计算)
        close_percent: 平仓百分比 (默认100%全部平仓)
        activation_price: 激活价格 (可选，价格达到此点开始跟踪)
        user_id: 用户ID
    
    Returns:
        dict with order info
    
    Example:
        # BTC 多头设置 1% 跟踪止损
        place_trailing_stop("BTC", callback_rate=1.0)
        
        # ETH 设置 0.5% 跟踪止损，激活价格 4000
        place_trailing_stop("ETH", callback_rate=0.5, activation_price=4000)
    """
    user_id = _get_effective_user_id(user_id)
    symbol = get_symbol_usdt(symbol)
    
    # Get trading client (supports both user_binance_keys and exchange_accounts)
    client, err = _get_trading_client(user_id)
    if err:
        return {"error": err}
    
    # 验证回调比例
    if callback_rate < 0.1 or callback_rate > 5:
        return {"error": "Callback rate must be between 0.1 and 5 (percent)"}
    
    try:
        # 获取当前持仓
        positions = client.get_positions()
        if isinstance(positions, dict) and "error" in positions:
            return {"error": f"Failed to get positions: {positions['error']}"}
        
        position = None
        for p in positions:
            if p.get("symbol") == symbol:
                pos_amt = float(p.get("positionAmt", 0))
                if pos_amt != 0:
                    position = p
                    break
        
        if not position:
            return {"error": f"No open position found for {symbol}"}
        
        pos_amt = float(position.get("positionAmt", 0))
        is_long = pos_amt > 0
        
        # Check Position Mode (One-Way or Hedge)
        try:
            mode_resp = client.get_position_mode()
            is_hedge_mode = mode_resp.get("dualSidePosition", False) if isinstance(mode_resp, dict) else False
        except Exception as e:
            print(f"[BinanceTrading] Check position mode failed: {e}")
            is_hedge_mode = False
        
        # 计算平仓数量
        if quantity:
            close_qty = abs(quantity)
        else:
            close_qty = abs(pos_amt) * (close_percent / 100)
        
        close_qty = round_quantity(symbol, close_qty)
        
        # 多头用 SELL，空头用 BUY
        side = "SELL" if is_long else "BUY"
        
        # Determine positionSide and reduceOnly based on mode
        # Hedge Mode: use positionSide, NOT reduceOnly
        # One-Way Mode: use reduceOnly, NOT positionSide
        position_side = ("LONG" if is_long else "SHORT") if is_hedge_mode else None
        use_reduce_only = not is_hedge_mode
        
        result = client.place_trailing_stop_order(
            symbol=symbol,
            side=side,
            quantity=close_qty,
            callback_rate=callback_rate,
            activation_price=activation_price,
            reduce_only=use_reduce_only,
            position_side=position_side
        )
        
        if isinstance(result, dict) and "error" in result:
            return {"error": f"Failed to place trailing stop: {result['error']}"}
        
        return {
            "success": True,
            "order_id": result.get("orderId"),
            "symbol": symbol,
            "side": side,
            "quantity": close_qty,
            "callback_rate": callback_rate,
            "activation_price": activation_price,
            "position_side": "LONG" if is_long else "SHORT",
            "message": f"Trailing stop set: {callback_rate}% callback"
        }
        
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def binance_get_position_mode(user_id: str = None) -> dict:
    """
    获取当前持仓模式。
    
    使用方法:
        get_position_mode()
    
    Returns:
        dict with position mode info:
        - dual_side: True = 对冲模式, False = 单向模式
    """
    user_id = _get_effective_user_id(user_id)
    
    client, err = _get_trading_client(user_id, require_trading_enabled=False)
    if err:
        return {"error": err}
    
    try:
        result = client.get_position_mode()
        
        if isinstance(result, dict) and "error" in result:
            return {"error": f"Failed to get position mode: {result['error']}"}
        
        dual_side = result.get("dualSidePosition", False)
        
        return {
            "success": True,
            "dual_side": dual_side,
            "mode": "对冲模式 (Hedge Mode)" if dual_side else "单向模式 (One-way Mode)",
            "description": "可同时持有多空仓位" if dual_side else "只能持有单边仓位"
        }
        
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def binance_change_position_mode(
    dual_side: bool,
    user_id: str = None
) -> dict:
    """
    切换持仓模式。
    
    ⚠️ 注意：切换前必须平掉所有仓位！
    
    使用方法:
        change_position_mode(True)   # 切换到对冲模式
        change_position_mode(False)  # 切换到单向模式
    
    Args:
        dual_side: True = 对冲模式, False = 单向模式
    
    Returns:
        dict with operation result
    """
    user_id = _get_effective_user_id(user_id)
    
    client, err = _get_trading_client(user_id, require_trading_enabled=True)
    if err:
        return {"error": err}
    
    try:
        # 先检查是否有持仓
        positions = client.get_positions()
        if isinstance(positions, list):
            for p in positions:
                if float(p.get("positionAmt", 0)) != 0:
                    return {
                        "error": "Cannot change position mode while holding positions. Please close all positions first.",
                        "holding_position": p.get("symbol")
                    }
        
        result = client.change_position_mode(dual_side)
        
        if isinstance(result, dict) and "error" in result:
            return {"error": f"Failed to change position mode: {result['error']}"}
        
        mode_name = "对冲模式 (Hedge Mode)" if dual_side else "单向模式 (One-way Mode)"
        
        return {
            "success": True,
            "dual_side": dual_side,
            "mode": mode_name,
            "message": f"Successfully switched to {mode_name}"
        }
        
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}




def calculate_position_size(
    symbol: str, 
    stop_loss: float, 
    risk_percent: float = 5.0,  # 提高默认风险比例到 5%
    entry_price: float = None, 
    leverage: int = 10,  # 提高默认杠杆到 10x
    user_id: str = None,
    min_risk_amount: float = 10.0,  # 新增：最小风险金额 (USD)，小账户保护
    max_risk_amount: float = 200.0,  # 单笔最大亏损金额硬顶 (USD)
    max_position_leverage: float = 15.0 # 提高最大有效杠杆到 15x
) -> dict:
    """
    基于风险金额计算建议仓位大小（小资金友好）。
    
    核心逻辑:
    1. 计算基于百分比的风险金额: Equity * (risk_percent / 100)
    2. 应用最小/最大风险金额限制: min_risk_amount <= risk <= max_risk_amount
    3. 小账户时，使用 min_risk_amount 确保仓位有意义
    
    公式: Position Size = Risk Amount / (Entry Price - Stop Loss)
    
    小资金思路:
    - 不是看百分比亏多少，而是看绝对金额亏多少
    - 有杠杆放大仓位，小资金也能做出有意义的交易
    
    Args:
        symbol: 交易对
        stop_loss: 止损价格
        risk_percent: 风险比例 (默认 5%)
        entry_price: 入场价
        leverage: 交易所杠杆倍数 (默认 10x)
        user_id: 用户ID
        min_risk_amount: 风险金额下限 (USD), 默认 $10，确保小账户也能开出有意义的仓位
        max_risk_amount: 风险金额上限 (USD), 默认 $200
        max_position_leverage: 有效杠杆上限 (防止过窄止损导致仓位过大), 默认 15x
    
    Returns:
        dict
    """
    user_id = _get_effective_user_id(user_id)
    symbol = get_symbol_usdt(symbol)
    
    if stop_loss <= 0:
        return {"error": "Stop loss price must be positive"}
    if risk_percent <= 0 or risk_percent > 100:
        return {"error": "Risk percent must be between 0 and 100"}
        
    client = get_user_binance_client(user_id)
    if not client:
        return {"error": "Failed to create Binance client"}
        
    # 1. Get Equity (Margin Balance)
    balance_info = binance_get_usdt_balance(user_id)
    if "error" in balance_info:
        return {"error": f"Failed to get balance: {balance_info['error']}"}
        
    equity = float(balance_info.get("margin_balance", 0))
    if equity <= 0:
        return {"error": f"Account equity (${equity}) is not enough"}
        
    # 2. Get Entry Price
    if not entry_price:
        current_price = binance_get_current_price(symbol, user_id)
        if isinstance(current_price, dict) and "error" in current_price:
             return {"error": f"Failed to get current price: {current_price.get('error')}"}
        elif isinstance(current_price, (int, float)) and current_price <= 0:
             return {"error": "Invalid current price"}
        entry_price = float(current_price)
        
    if entry_price <= 0:
        return {"error": "Invalid entry price"}
        
    # 3. Calculate Risk Amount (Initial)
    risk_amount = equity * (risk_percent / 100.0)
    
    # [小资金保护] 应用最小风险金额
    # 小账户时，使用 min_risk_amount 确保仓位有意义
    if risk_amount < min_risk_amount:
        risk_amount = min_risk_amount
    
    # [SAFETY 1] Apply Max Risk Amount Hard Cap
    if risk_amount > max_risk_amount:
        # print(f"Risk amount ${risk_amount:.2f} capped at ${max_risk_amount:.2f}")
        risk_amount = max_risk_amount
    
    # 4. Calculate Distance
    price_distance = abs(entry_price - stop_loss)
    if price_distance == 0:
        return {"error": "Stop loss cannot be equal to entry price"}
    
    # 价格距离百分比
    dist_pct = (price_distance / entry_price) * 100
    if dist_pct < 0.2: # 防止过窄止损导致巨大仓位
         return {"error": f"Stop loss too close ({dist_pct:.2f}% < 0.2%). Position size would be dangerous."}

    # 5. Calculate Position Size (in Coins)
    raw_quantity = risk_amount / price_distance
    
    # [SAFETY 2] Check Effective Leverage (Notional / Equity)
    # 即使风险金额很小，如果止损太窄 (e.g. 0.3%)，仓位名义价值可能非常大 (e.g. >20x Equity)
    implied_notional = raw_quantity * entry_price
    effective_leverage = implied_notional / equity
    
    leverage_warning = ""
    if effective_leverage > max_position_leverage:
        # 限制仓位大小，使其不超过最大有效杠杆
        capped_notional = equity * max_position_leverage
        capped_quantity = capped_notional / entry_price
        
        leverage_warning = f" (Reduced from {raw_quantity:.4f} due to max leverage {max_position_leverage}x)"
        raw_quantity = capped_quantity
        # Recalculate risk based on new quantity
        new_risk = raw_quantity * price_distance
        risk_amount = new_risk

    # Round quantity valid for binance
    quantity = round_quantity(symbol, raw_quantity)
    
    # Check min order size
    min_qty = get_min_order_size(symbol)
    if quantity < min_qty:
        return {
            "error": f"Calculated position size ({quantity}) is below minimum ({min_qty}). Risk amount (${risk_amount:.2f}) is too small for this wide stop."
        }

    # 6. Calculate Notional & Margin
    notional_value = quantity * entry_price
    required_margin = notional_value / leverage
    
    # Check if we have enough margin?
    available = float(balance_info.get("available_balance", 0))
    margin_check = "OK"
    if required_margin > available:
        margin_check = "INSUFFICIENT"
    
    return {
        "success": True,
        "symbol": symbol,
        "side": "LONG" if entry_price > stop_loss else "SHORT",
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "risk_percent": risk_percent,
        "account_equity": equity,
        "risk_amount": round(risk_amount, 2),
        "actual_risk_pct": round(risk_amount / equity * 100, 2),
        "quantity": quantity,
        "effective_leverage": round(effective_leverage, 2),
        "leverage": leverage,
        "required_margin": round(required_margin, 2),
        "available_balance": available,
        "margin_status": margin_check,
        "message": f"Suggestion: Open {quantity} {symbol}{leverage_warning} (Margin: ${required_margin:.2f}, Risk: ${risk_amount:.2f})"
    }


# ==========================================
# 孤儿订单清理
# ==========================================

def binance_cancel_orphan_orders(user_id: str = None) -> dict:
    """
    扫描并清理孤儿订单：即已经没有对应持仓的止损/止盈/条件挂单。
    
    当仓位被止损或止盈触发自动平仓时，另一侧的挂单不会被自动取消。
    此函数会定期检测这种情况并清理这些孤儿订单，避免它们在后续
    新开仓时被错误触发。
    
    Args:
        user_id: 用户ID
    
    Returns:
        dict with cleanup results
    """
    user_id = _get_effective_user_id(user_id)
    
    client, err = _get_trading_client(user_id, require_trading_enabled=False)
    if err:
        return {"error": err}
    
    try:
        # 1. 获取当前所有持仓的 symbols
        positions = client.get_positions()
        if isinstance(positions, dict) and "error" in positions:
            return {"error": f"Failed to get positions: {positions['error']}"}
        
        position_symbols = set()
        for pos in (positions if isinstance(positions, list) else []):
            symbol = pos.get("symbol", "")
            if symbol:
                position_symbols.add(symbol)
        
        # 2. 获取所有普通挂单
        open_orders = client.get_open_orders()
        normal_orphans = []
        if isinstance(open_orders, list):
            for order in open_orders:
                order_symbol = order.get("symbol", "")
                order_type = order.get("type", "")
                # 只清理 reduceOnly 或条件类订单（STOP_MARKET, TAKE_PROFIT_MARKET 等）
                # 不清理主动的限价开仓单
                is_conditional = order_type in ("STOP_MARKET", "TAKE_PROFIT_MARKET", "STOP", "TAKE_PROFIT", "TRAILING_STOP_MARKET")
                is_reduce = str(order.get("reduceOnly", "")).lower() == "true"
                
                if (is_conditional or is_reduce) and order_symbol not in position_symbols:
                    normal_orphans.append(order)
        
        # 3. 获取所有 Algo/条件挂单
        algo_orders = []
        try:
            algo_result = client.get_open_algo_orders()
            if isinstance(algo_result, list):
                algo_orders = algo_result
        except Exception:
            pass
        
        algo_orphans = []
        for order in algo_orders:
            order_symbol = order.get("symbol", "")
            if order_symbol not in position_symbols:
                algo_orphans.append(order)
        
        # 4. 取消孤儿订单
        cancelled_normal = 0
        cancelled_algo = 0
        errors = []
        
        # 按 symbol 分组取消普通孤儿订单
        orphan_symbols = set(o.get("symbol", "") for o in normal_orphans)
        for sym in orphan_symbols:
            if sym:
                try:
                    client.cancel_all_orders(sym)
                    cancelled_normal += len([o for o in normal_orphans if o.get("symbol") == sym])
                except Exception as e:
                    errors.append(f"cancel_normal({sym}): {e}")
        
        # 逐个取消 Algo 孤儿订单
        for order in algo_orphans:
            algo_id = order.get("algoId")
            if algo_id:
                try:
                    result = client._request("DELETE", "/fapi/v1/algoOrder", {"algoId": algo_id})
                    if isinstance(result, dict) and "error" not in result:
                        cancelled_algo += 1
                    else:
                        errors.append(f"cancel_algo({algo_id}): {result}")
                except Exception as e:
                    errors.append(f"cancel_algo({algo_id}): {e}")
        
        total = cancelled_normal + cancelled_algo
        if total > 0:
            print(f"[OrphanCleanup] Cleaned {total} orphan orders for user {user_id[:8]} "
                  f"(normal={cancelled_normal}, algo={cancelled_algo})")
        
        return {
            "success": True,
            "position_symbols": list(position_symbols),
            "orphan_normal_count": len(normal_orphans),
            "orphan_algo_count": len(algo_orphans),
            "cancelled_normal": cancelled_normal,
            "cancelled_algo": cancelled_algo,
            "errors": errors if errors else None
        }
        
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


# ==========================================
# Generic Aliases (exchange-agnostic names)
# New code should use these instead of binance_ prefixed names.
# ==========================================

open_position = binance_open_position
close_position = binance_close_position
get_usdt_balance = binance_get_usdt_balance
get_positions_summary = binance_get_positions_summary
get_current_price = binance_get_current_price
update_stop_loss = binance_update_stop_loss
update_take_profit = binance_update_take_profit
get_open_orders = binance_get_open_orders
modify_order = binance_modify_order
get_income_history = binance_get_income_history
get_funding_rate = binance_get_funding_rate
get_adl_risk = binance_get_adl_risk
get_force_orders = binance_get_force_orders
get_leverage_info = binance_get_leverage_info
get_commission_rate = binance_get_commission_rate
place_trailing_stop = binance_place_trailing_stop
get_position_mode = binance_get_position_mode
change_position_mode = binance_change_position_mode
cancel_orphan_orders = binance_cancel_orphan_orders
