"""
订单管理：止损/止盈更新、挂单查询、订单修改、收入历史、资金费率
"""
from tools.trading._client import _get_effective_user_id, _get_trading_client
from tools.trading._config import *
from binance_client import get_user_binance_client

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

