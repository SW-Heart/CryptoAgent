"""
订单清理：扫描并清理孤儿订单
"""
from tools.trading._client import _get_effective_user_id, _get_trading_client

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

