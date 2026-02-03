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
    client = get_user_binance_client(user_id)
    if not client:
        return {"error": "Failed to create client"}
    
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
                "price": str(price),
                "positionSide": position_side
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
                "quantity": str(quantity),
                "positionSide": position_side
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
                    "positionSide": position_side, # SL orders need positionSide too? Yes.
                    "closePosition": "true" if is_hedge_mode else "false", # Hedge Mode specific
                    # Note: For One-Way Mode, closePosition=true is NOT supported in batch? 
                    # Use reduceOnly=true for One-Way.
                })
                # Fix for params:
                if not is_hedge_mode:
                     orders[-1]["reduceOnly"] = "true"
                     del orders[-1]["closePosition"]
                else:
                     # For Hedge Mode SL, usually type=STOP_MARKET, closePosition=true works?
                     # Let's verify. API says "closePosition=true" works for STOP_MARKET.
                     pass
            
            # 3. 止盈单 (if specified, only for Market)
            if take_profit:
                take_profit = round_price(symbol, take_profit)
                orders.append({
                    "symbol": symbol,
                    "side": close_side,
                    "type": "TAKE_PROFIT_MARKET",
                    "quantity": str(quantity),
                    "stopPrice": str(take_profit),
                    "positionSide": position_side,
                    "closePosition": "true" if is_hedge_mode else "false"
                })
                if not is_hedge_mode:
                     orders[-1]["reduceOnly"] = "true"
                     del orders[-1]["closePosition"]
        
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
    
    if not has_user_api_keys(user_id):
        return {"error": "Please configure your Binance API keys first"}
    
    client = get_user_binance_client(user_id)
    if not client:
        return {"error": "Failed to create Binance client"}
    
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
        if has_user_api_keys(user_id):
            client = get_user_binance_client(user_id)
    
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
    
    if not has_user_api_keys(user_id):
        return {"error": "Please configure your Binance API keys first"}
    
    client = get_user_binance_client(user_id)
    if not client:
        return {"error": "Failed to create Binance client"}
    
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
    
    if not has_user_api_keys(user_id):
        return {"error": "Please configure your Binance API keys first"}
    
    client = get_user_binance_client(user_id)
    if not client:
        return {"error": "Failed to create Binance client"}
    
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
    
    if not has_user_api_keys(user_id):
        return {"error": "Please configure your Binance API keys first"}
    
    client = get_user_binance_client(user_id)
    if not client:
        return {"error": "Failed to create Binance client"}
    
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
    
    if not has_user_api_keys(user_id):
        return {"error": "Please configure your Binance API keys first"}
    
    client = get_user_binance_client(user_id)
    if not client:
        return {"error": "Failed to create Binance client"}
    
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
    
    if not has_user_api_keys(user_id):
        return {"error": "Please configure your Binance API keys first"}
    
    status = get_user_trading_status(user_id)
    if not status.get("is_trading_enabled"):
        return {"error": "Trading is not enabled"}
    
    client = get_user_binance_client(user_id)
    if not client:
        return {"error": "Failed to create Binance client"}
    
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
        
        # 计算平仓数量
        if quantity:
            close_qty = abs(quantity)
        else:
            close_qty = abs(pos_amt) * (close_percent / 100)
        
        close_qty = round_quantity(symbol, close_qty)
        
        # 多头用 SELL，空头用 BUY
        side = "SELL" if is_long else "BUY"
        
        result = client.place_trailing_stop_order(
            symbol=symbol,
            side=side,
            quantity=close_qty,
            callback_rate=callback_rate,
            activation_price=activation_price,
            reduce_only=True
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
    
    if not has_user_api_keys(user_id):
        return {"error": "Please configure your Binance API keys first"}
    
    client = get_user_binance_client(user_id)
    if not client:
        return {"error": "Failed to create Binance client"}
    
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
    
    if not has_user_api_keys(user_id):
        return {"error": "Please configure your Binance API keys first"}
    
    client = get_user_binance_client(user_id)
    if not client:
        return {"error": "Failed to create Binance client"}
    
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
    risk_percent: float = 1.0, 
    entry_price: float = None, 
    leverage: int = 5,
    user_id: str = None,
    max_risk_amount: float = 200.0,  # 新增：单笔最大亏损金额硬顶 (USD)
    max_position_leverage: float = 10.0 # 新增：最大允许的有效杠杆 (Effective Leverage)
) -> dict:
    """
    基于账户权益和风险百分比计算建议仓位大小。
    
    公式: Risk Amount = Equity * (risk_percent / 100)
    
    安全机制:
    1. Hard Cap: 风险金额不超过 max_risk_amount
    2. Leverage Check: 有效杠杆不超过 max_position_leverage
    
    Args:
        symbol: 交易对
        stop_loss: 止损价格
        risk_percent: 风险比例 (1%)
        entry_price: 入场价
        leverage: 交易所杠杆倍数 (仅用于计算保证金)
        user_id: 用户ID
        max_risk_amount: 风险金额上限 (USD), 默认 $200
        max_position_leverage: 有效杠杆上限 (防止过窄止损导致仓位过大), 默认 10倍
    
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
