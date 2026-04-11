"""
Position Builder — Trade-based Position History Reconstruction

Reconstructs closed position records from raw trade history.
Decoupled from the router layer for testability and reuse.

Algorithm (inspired by nofx/trader/position_rebuild.go):
  1. Sort trades by time ascending
  2. RealizedPnL == 0 → opening trade → accumulate into current position
  3. RealizedPnL != 0 → closing trade → deduct from current position
  4. When close_qty >= entry_qty (with 1% tolerance) → emit ClosedPosition record
  5. Reset and repeat for next position cycle

Usage:
    from position_builder import build_position_history
    
    trades = client.get_trade_history(symbol="BTCUSDT", limit=200)
    closed_positions = build_position_history(trades, symbol="BTCUSDT")
"""

from typing import List, Dict, Optional


def build_position_history(
    trades: List[dict],
    symbol: str,
    default_leverage: int = 10,
    close_tolerance: float = 0.99,
) -> List[dict]:
    """
    从成交记录聚合出仓位级别的历史数据。
    
    Args:
        trades: 成交记录列表（必须是统一格式，含 side/qty/price/realizedPnl/commission/time）
        symbol: 交易对（如 BTCUSDT）
        default_leverage: 默认杠杆（用于计算 ROI，当无法从 trade 中获取时）
        close_tolerance: 平仓完成度容差（0.99 = 平仓量达到开仓量的 99% 即视为全平）
    
    Returns:
        已平仓仓位列表，按平仓时间倒序排列
    """
    if not trades:
        return []
    
    # 按时间正序排列以便追踪仓位生命周期
    sorted_trades = sorted(trades, key=lambda x: x.get("time", 0))
    
    positions = []
    current_pos: Optional[dict] = None
    
    for trade in sorted_trades:
        side = trade.get("side", "")
        qty = float(trade.get("qty", 0))
        price = float(trade.get("price", 0))
        r_pnl = float(trade.get("realizedPnl", 0))
        commission = float(trade.get("commission", 0))
        trade_time = trade.get("time", 0)
        
        if qty <= 0 or price <= 0:
            continue
        
        if current_pos is None:
            # 开新仓
            current_pos = _new_position(symbol, side, trade_time, default_leverage)
        
        # 判断这笔交易是开仓还是平仓
        is_opening = _is_opening_trade(current_pos["direction"], side)
        
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
        
        # 如果已平仓量 >= 开仓量 × 容差，仓位周期结束
        if _is_position_closed(current_pos, close_tolerance):
            closed = _finalize_position(current_pos)
            if closed:
                positions.append(closed)
            current_pos = None
    
    # 按平仓时间倒序排列
    positions.sort(key=lambda x: x.get("close_time", 0), reverse=True)
    return positions


def _new_position(symbol: str, side: str, open_time: int, leverage: int) -> dict:
    """创建新的仓位追踪结构。"""
    return {
        "symbol": symbol,
        "direction": "LONG" if side == "BUY" else "SHORT",
        "entry_trades": [],
        "close_trades": [],
        "total_entry_qty": 0.0,
        "total_entry_cost": 0.0,
        "total_close_qty": 0.0,
        "total_close_cost": 0.0,
        "realized_pnl": 0.0,
        "total_commission": 0.0,
        "open_time": open_time,
        "close_time": None,
        "leverage": leverage,
    }


def _is_opening_trade(direction: str, side: str) -> bool:
    """判断一笔交易是否为开仓方向。"""
    return (direction == "LONG" and side == "BUY") or \
           (direction == "SHORT" and side == "SELL")


def _is_position_closed(pos: dict, tolerance: float) -> bool:
    """判断仓位是否已完全平仓。"""
    if pos["total_close_qty"] <= 0 or pos["total_entry_qty"] <= 0:
        return False
    return pos["total_close_qty"] >= pos["total_entry_qty"] * tolerance


def _finalize_position(pos: dict) -> Optional[dict]:
    """
    将内部追踪结构转换为前端可用的已平仓仓位记录。
    
    Returns:
        格式化的仓位记录 dict，或 None（如果数据无效）
    """
    if pos["total_entry_qty"] <= 0:
        return None
    
    entry_price = pos["total_entry_cost"] / pos["total_entry_qty"]
    close_price = (pos["total_close_cost"] / pos["total_close_qty"]) \
        if pos["total_close_qty"] > 0 else 0.0
    
    # 计算收益率（基于开仓保证金）
    entry_notional = pos["total_entry_qty"] * entry_price
    margin = entry_notional / pos["leverage"] if pos["leverage"] > 0 else entry_notional
    roi = (pos["realized_pnl"] / margin * 100) if margin > 0 else 0
    
    sym = pos["symbol"]
    sym_short = sym.replace("USDT", "") if sym.endswith("USDT") else sym
    
    return {
        "symbol": sym_short,
        "symbol_full": sym,
        "direction": pos["direction"],
        "leverage": pos["leverage"],
        "margin_mode": "全仓",
        "close_type": "全部平仓",
        "realized_pnl": round(pos["realized_pnl"], 4),
        "roi_percent": round(roi, 2),
        "closed_quantity": pos["total_close_qty"],
        "entry_price": round(entry_price, 2),
        "close_price": round(close_price, 2),
        "max_quantity": pos["total_entry_qty"],
        "total_commission": round(pos["total_commission"], 4),
        "open_time": pos["open_time"],
        "close_time": pos["close_time"],
    }
