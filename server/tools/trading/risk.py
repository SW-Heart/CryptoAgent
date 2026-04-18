"""
风控功能：ADL 风险、强制平仓记录、杠杆信息、手续费率、仓位计算
"""
from tools.trading._client import _get_effective_user_id, _get_trading_client
from tools.trading._config import *
from binance_client import get_user_binance_client

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
                # 使用统一字段 quantity (正数) + direction，兼容所有交易所
                qty = float(p.get("quantity", 0))
                if qty != 0:
                    position = p
                    break
        
        if not position:
            return {"error": f"No open position found for {symbol}"}
        
        # 使用统一 direction 字段判断方向
        is_long = position.get("direction") == "LONG"
        pos_qty = float(position.get("quantity", 0))
        
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
            close_qty = pos_qty * (close_percent / 100)
        
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
                if float(p.get("quantity", p.get("positionAmt", 0))) != 0:
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

