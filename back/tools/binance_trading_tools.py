"""
Binance Trading Tools for Strategy Nexus
Real contract trading using Binance Futures API.

This module replaces the virtual trading simulation with real Binance API calls.
Each user has their own API keys and trading status.

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

# Price decimal places for common pairs (Binance Futures Testnet requirements)
PRICE_PRECISION = {
    "BTCUSDT": 1,   # Testnet: 1 decimal
    "ETHUSDT": 2,
    "SOLUSDT": 2,   # Testnet: 2 decimals (not 3!)
    "BNBUSDT": 2,
    "XRPUSDT": 4,
    "DOGEUSDT": 5,
    "DEFAULT": 2
}

# Quantity decimal places for common pairs (Binance Futures Testnet requirements)
QTY_PRECISION = {
    "BTCUSDT": 3,
    "ETHUSDT": 3,
    "SOLUSDT": 0,   # Testnet: integer only (0 decimals)
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
    
    # Check user trading status
    if not has_user_api_keys(user_id):
        return {"error": "Please configure your Binance API keys first"}
    
    status = get_user_trading_status(user_id)
    if not status.get("is_trading_enabled"):
        return {"error": "Trading is not enabled. Please enable trading first."}
    
    # Get client
    client = get_user_binance_client(user_id)
    if not client:
        return {"error": "Failed to create Binance client"}
    
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
        
        # Check minimum order size
        min_size = get_min_order_size(symbol)
        if quantity < min_size:
            return {"error": f"Order size {quantity} is below minimum {min_size} for {symbol}"}
        
        # Determine side
        side = "BUY" if direction == "LONG" else "SELL"
        close_side = "SELL" if direction == "LONG" else "BUY"
        
        # Build batch orders
        orders = []
        
        # 1. 开仓单 (Main Order)
        if order_type == "LIMIT":
            # Limit Order
            price = round_price(symbol, price)
            orders.append({
                "symbol": symbol,
                "side": side,
                "type": "LIMIT",
                "timeInForce": "GTC", # Good Till Cancel
                "quantity": str(quantity),
                "price": str(price)
            })
            
            # NOTE: For Limit orders, we cannot safely attach SL/TP in the same batch 
            # because the entry might not fill immediately, and reduceOnly orders 
            # might be rejected or trigger inappropriately.
            if stop_loss or take_profit:
                print(f"[BinanceTrading] WARNING: SL/TP ignored for LIMIT order on {symbol}. "
                      f"Please manage risk manually after fill.")
        else:
            # Market Order
            orders.append({
                "symbol": symbol,
                "side": side,
                "type": "MARKET",
                "quantity": str(quantity)
            })
            
            # 2. 止损单 (if specified, only for Market)
            if stop_loss:
                stop_loss = round_price(symbol, stop_loss)
                orders.append({
                    "symbol": symbol,
                    "side": close_side,
                    "type": "STOP_MARKET",
                    "quantity": str(quantity),
                    "stopPrice": str(stop_loss),
                    "reduceOnly": "true"
                })
            
            # 3. 止盈单 (if specified, only for Market)
            if take_profit:
                take_profit = round_price(symbol, take_profit)
                orders.append({
                    "symbol": symbol,
                    "side": close_side,
                    "type": "TAKE_PROFIT_MARKET",
                    "quantity": str(quantity),
                    "stopPrice": str(take_profit),
                    "reduceOnly": "true"
                })
        
        print(f"[BinanceTrading] Placing batch orders: {len(orders)} orders (Type: {order_type})")
        
        # Use batch orders API for atomic execution
        batch_result = client.place_batch_orders(orders)
        
        if isinstance(batch_result, dict) and "error" in batch_result:
            return {"error": f"Batch order failed: {batch_result['error']}"}
        
        if not isinstance(batch_result, list):
            return {"error": f"Unexpected batch result: {batch_result}"}
        
        # Parse results
        order_id = None
        sl_order_id = None
        tp_order_id = None
        avg_price = 0
        executed_qty = 0
        
        for i, result in enumerate(batch_result):
            if "error" in result or "code" in result:
                print(f"[BinanceTrading] Order {i+1} failed: {result}")
                continue
            
            res_type = result.get("type", "")
            if res_type == "MARKET" or res_type == "LIMIT":
                order_id = result.get("orderId")
                avg_price = float(result.get("avgPrice", 0) or 0)
                executed_qty = float(result.get("executedQty", 0) or 0)
            elif res_type == "STOP_MARKET":
                sl_order_id = result.get("orderId")
            elif res_type == "TAKE_PROFIT_MARKET":
                tp_order_id = result.get("orderId")
        
        # Check if main order succeeded
        if not order_id:
            return {"error": "Failed to place order"}
        
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
    
    # Check user trading status
    if not has_user_api_keys(user_id):
        return {"error": "Please configure your Binance API keys first"}
    
    status = get_user_trading_status(user_id)
    if not status.get("is_trading_enabled"):
        return {"error": "Trading is not enabled"}
    
    # Get client
    client = get_user_binance_client(user_id)
    if not client:
        return {"error": "Failed to create Binance client"}
    
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
        
        # Determine side (opposite of position direction)
        side = "SELL" if direction == "LONG" else "BUY"
        
        # Place market order to close
        order_result = client.place_market_order(
            symbol, side, close_qty, reduce_only=True
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
        
        # Cancel associated SL/TP orders if fully closed
        if close_percent == 100:
            try:
                client.cancel_all_orders(symbol)
            except Exception as e:
                print(f"[BinanceTrading] Failed to cancel orders: {e}")
        
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
    
    # Check user status
    if not has_user_api_keys(user_id):
        print(f"[BinanceTools] API keys NOT found for user: {user_id}")
        return {
            "error": "API keys not configured",
            "is_configured": False,
            "debug_user_id": user_id  # 添加调试信息
        }
    
    status = get_user_trading_status(user_id)
    
    # Get client
    client = get_user_binance_client(user_id)
    if not client:
        return {"error": "Failed to create Binance client"}
    
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
    
    # Fallback to public API
    import requests
    try:
        url = f"https://testnet.binancefuture.com/fapi/v1/premiumIndex?symbol={symbol}"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        return float(data.get("markPrice", 0))
    except Exception as e:
        print(f"[BinanceTrading] Price fetch error for {symbol}: {e}")
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
    
    client = get_user_binance_client(user_id)
    if not client:
        return {"error": "Failed to create Binance client"}
    
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
        
        # Cancel existing orders
        client.cancel_all_orders(symbol)
        
        # Place new SL order
        new_stop_loss = round_price(symbol, new_stop_loss)
        sl_side = "SELL" if direction == "LONG" else "BUY"
        sl_result = client.place_stop_market_order(
            symbol, sl_side, quantity, new_stop_loss
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
