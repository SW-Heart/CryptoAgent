"""
持仓操作：开仓、平仓、持仓汇总、获取价格
"""
from tools.trading._client import _get_effective_user_id, _get_trading_client
from tools.trading._config import *
from binance_client import get_user_binance_client, get_user_trading_status
from tools.trading_tools import add_session_action
import requests

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
        
        # Record session action for accurate decision logging
        add_session_action(f"OPEN_{direction}_{symbol}")
        
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
        
        # Record session action for accurate decision logging
        if close_percent >= 100:
            add_session_action(f"CLOSE_{direction}_{symbol}")
        else:
            add_session_action(f"PARTIAL_CLOSE_{direction}_{symbol}_{int(close_percent)}%")
        
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


