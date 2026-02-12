"""
Trading Tools for Strategy Nexus
Virtual contract trading simulation using Binance real-time prices.
"""
import sqlite3
from datetime import datetime
import requests

DB_PATH = "tmp/test.db"

# ==========================================
# Access Control
# ==========================================
STRATEGY_ADMIN_USER_ID = "ee20fa53-5ac2-44bc-9237-41b308e291d8"

# Context variable for current request (works correctly in async environments)
# threading.local() doesn't work well with async/await, use contextvars instead
from contextvars import ContextVar
_current_user_id: ContextVar[str] = ContextVar('current_user_id', default=None)

def set_current_user(user_id: str):
    """Set the current user ID for this request (async-safe)"""
    _current_user_id.set(user_id)
    print(f"[TradingTools] Context set user_id: {user_id[:8] if user_id else 'None'}...")

def get_current_user() -> str:
    """Get the current user ID for this request (async-safe)"""
    user_id = _current_user_id.get()
    print(f"[TradingTools] Context get user_id: {user_id[:8] if user_id else 'None'}...")
    return user_id

def is_admin(user_id: str = None) -> bool:
    """Check if user is the strategy admin. Uses context user if not provided."""
    if user_id is None:
        user_id = get_current_user()
    return user_id == STRATEGY_ADMIN_USER_ID

from app.database import get_db_connection as get_db

# get_db function removed, using imported one

def get_current_price(symbol: str) -> float:
    """Get current price from Binance"""
    import os
    binance_base = os.getenv("BINANCE_API_BASE", "https://api.binance.com")
    try:
        resp = requests.get(
            f"{binance_base}/api/v3/ticker/price?symbol={symbol.upper()}USDT",
            timeout=5
        )
        if resp.status_code != 200:
             print(f"[TradingTools] Price fetch failed {resp.status_code}: {resp.text}")
             return 0
        return float(resp.json().get("price", 0))
    except Exception as e:
        print(f"[TradingTools] Price fetch error for {symbol}: {e}")
        return 0
        print(f"[TradingTools] Price fetch error for {symbol}: {e}")
        return 0


# ==========================================
# Agent Tools
# ==========================================

def log_strategy_analysis(
    symbols: str,
    market_analysis: str,
    position_check: str,
    strategy_decision: str,
    action_taken: str = "HOLD",
    user_id: str = None
) -> dict:
    """
    Log strategy analysis results to database. Admin only.
    
    Args:
        symbols: Analyzed symbols (e.g., "BTC,ETH,SOL")
        market_analysis: Summary of market analysis
        position_check: Current position status
        strategy_decision: Final decision and reasoning
        action_taken: Action taken (OPEN_LONG, OPEN_SHORT, CLOSE, ADJUST, HOLD)
        user_id: User ID for permission check
    
    Returns:
        dict with log confirmation
    """
    conn = get_db()
    with conn.cursor() as cursor:
        round_id = datetime.now().strftime("%Y-%m-%d_%H:%M")
        
        # Check if a log for the same symbols exists within last 3 minutes (avoid duplicates)
        # 注意: "timestamp" 是 PostgreSQL 保留字，且可能是 TEXT 类型 (如在旧表中)，需显式转换
        cursor.execute("""
            SELECT 1 FROM strategy_logs 
            WHERE symbols = %s 
            AND "timestamp"::timestamp > NOW() - INTERVAL '3 minutes'
        """, (symbols,))
        existing = cursor.fetchone()
        
        if existing:
            conn.close()
            return {
                "success": True,
                "round_id": round_id,
                "message": f"Strategy log for {symbols} already exists (skipped duplicate)"
            }
        
        cursor.execute("""
            INSERT INTO strategy_logs (round_id, symbols, market_analysis, position_check, strategy_decision, actions_taken, raw_response)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            round_id,
            symbols,
            market_analysis[:2000] if market_analysis else "",
            position_check[:1000] if position_check else "",
            strategy_decision[:1000] if strategy_decision else "",
            f'["{action_taken}"]',
            f"Strategy analysis at {round_id}: {strategy_decision[:500]}"
        ))
        conn.commit()
    conn.close()
    
    return {
        "success": True,
        "round_id": round_id,
        "message": f"Strategy log saved for {symbols}"
    }


def open_position(
    symbol: str,
    direction: str,
    margin: float,
    leverage: int = 10,
    stop_loss: float = None,
    take_profit: float = None,  # 兼容旧接口，等同于 tp1_price
    tp1_price: float = None,
    tp2_price: float = None,
    tp3_price: float = None,
    tp1_percent: int = 50,  # TP1 平仓比例 (默认50%)
    tp2_percent: int = 30,  # TP2 平仓比例 (默认30%)
    tp3_percent: int = 20,  # TP3 平仓比例 (默认20%，即余仓)
    user_id: str = None
) -> dict:
    """
    Open a virtual contract position with leverage. Admin only.
    
    分批止盈配置：
    - 可设置 1-3 个止盈价位 (tp1_price, tp2_price, tp3_price)
    - 每个止盈对应平仓比例 (tp1_percent, tp2_percent, tp3_percent)
    - 比例之和应该等于 100%
    - 如果只设 tp1_price 且 tp1_percent=100，则一次性止盈
    
    示例：
    - 保守策略: tp1_price=3100, tp1_percent=80 (TP1平80%，剩余随走)
    - 标准策略: tp1_price=3100, tp2_price=3200, tp3_price=3300, tp1_percent=50, tp2_percent=30, tp3_percent=20
    - 极致策略: tp1_price=3100, tp1_percent=100 (一次性止盈)
    
    Args:
        symbol: Coin symbol (BTC, ETH, SOL)
        direction: LONG or SHORT
        margin: Margin (collateral) in USDT
        leverage: Leverage multiplier (default 10x)
        stop_loss: Stop loss price
        take_profit: Legacy param, same as tp1_price
        tp1_price: First take profit price (trigger partial close)
        tp2_price: Second take profit price (optional)
        tp3_price: Third take profit price (optional)
        tp1_percent: Percentage to close at TP1 (default 50)
        tp2_percent: Percentage to close at TP2 (default 30)
        tp3_percent: Percentage to close at TP3 (default 20)
        user_id: User ID for permission check
    
    Returns:
        dict with position details or error
    """
    symbol = symbol.upper()
    direction = direction.upper()
    
    if direction not in ["LONG", "SHORT"]:
        return {"error": "Direction must be LONG or SHORT"}
    
    if margin <= 0:
        return {"error": "Margin must be positive"}
    
    if leverage < 1 or leverage > 125:
        return {"error": "Leverage must be between 1 and 125"}
    
    # 兼容旧接口: take_profit -> tp1_price
    if take_profit and not tp1_price:
        tp1_price = take_profit
    
    # 验证止盈比例
    total_percent = 0
    if tp1_price:
        total_percent += tp1_percent
    if tp2_price:
        total_percent += tp2_percent
    if tp3_price:
        total_percent += tp3_percent
    
    if total_percent > 0 and total_percent != 100:
        return {"error": f"Take profit percentages must sum to 100%, got {total_percent}%"}
    
    conn = get_db()
    
    # 演示模式：所有操作都使用Admin账户
    effective_user = STRATEGY_ADMIN_USER_ID
    
    with conn.cursor() as cursor:
        # Check for duplicate position (same symbol and direction)
        cursor.execute(
            "SELECT id FROM positions WHERE user_id = %s AND symbol = %s AND direction = %s AND status = 'OPEN'",
            (effective_user, symbol, direction)
        )
        existing = cursor.fetchone()
        
        if existing:
            conn.close()
            return {"error": f"Already have an OPEN {direction} position on {symbol}. Cannot open duplicate."}
        
        # Check wallet balance for this user
        cursor.execute("SELECT current_balance FROM virtual_wallet WHERE user_id = %s", (effective_user,))
        wallet = cursor.fetchone()
        if not wallet:
            # Create wallet for new user with 0 balance
            cursor.execute("INSERT INTO virtual_wallet (user_id, initial_balance, current_balance) VALUES (%s, 0, 0)", (effective_user,))
            conn.commit()
            conn.close()
            return {"error": "Insufficient balance. Your wallet has 0 USDT."}
        
        available = wallet["current_balance"]
        
        # Check margin limit (max 20% of balance per position)
        if margin > available * 0.2:
            conn.close()
            return {"error": f"Margin {margin} exceeds 20% limit. Max allowed: {available * 0.2:.2f} USDT"}
        
        # Get current price first to calculate fee
        entry_price = get_current_price(symbol)
        if entry_price <= 0:
            conn.close()
            return {"error": f"Failed to get price for {symbol}"}
        
        # Calculate notional value and quantity
        notional_value = margin * leverage  # Total position value
        quantity = notional_value / entry_price  # Amount of coins
        
        # Calculate fee (0.05% of notional value)
        fee = notional_value * 0.0005
        
        # Check if margin + fee exceeds available (prevent overdraft)
        if margin + fee > available:
            conn.close()
            return {"error": f"Insufficient balance. Need {margin + fee:.2f} USDT (margin + fee), available: {available:.2f} USDT"}
        
        # Insert position with user_id and multi-TP fields
        cursor.execute("""
            INSERT INTO positions (
                user_id, symbol, direction, leverage, margin, notional_value, entry_price, quantity, 
                stop_loss, take_profit, current_price, status,
                tp1_price, tp2_price, tp3_price, tp1_percent, tp2_percent, tp3_percent,
                tp1_triggered, tp2_triggered, tp3_triggered
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'OPEN', %s, %s, %s, %s, %s, %s, 0, 0, 0)
            RETURNING id
        """, (effective_user, symbol, direction, leverage, margin, notional_value, entry_price, quantity, 
              stop_loss, tp1_price, entry_price,
              tp1_price, tp2_price, tp3_price, tp1_percent, tp2_percent, tp3_percent))
        
        position_id = cursor.fetchone()[0]
        
        # Insert order record - 开仓订单
        cursor.execute("""
            INSERT INTO orders (position_id, symbol, action, direction, quantity, margin, entry_price, stop_loss, take_profit, fee)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (position_id, symbol, f"OPEN_{direction}", direction, quantity, margin, entry_price, stop_loss, tp1_price, fee))
        
        # Deduct margin and fee from user's wallet (使用原子操作防止并发问题)
        cursor.execute("""
            UPDATE virtual_wallet 
            SET current_balance = current_balance - %s - %s, updated_at = CURRENT_TIMESTAMP 
            WHERE user_id = %s
        """, (margin, fee, effective_user))
        
        # 获取更新后的余额用于返回
        cursor.execute("SELECT current_balance FROM virtual_wallet WHERE user_id = %s", (effective_user,))
        new_balance_row = cursor.fetchone()
        new_balance = new_balance_row["current_balance"] if new_balance_row else 0
        
        conn.commit()
    conn.close()
    
    # Build take profit summary
    tp_summary = []
    if tp1_price:
        tp_summary.append(f"TP1: ${tp1_price:,.0f} ({tp1_percent}%)")
    if tp2_price:
        tp_summary.append(f"TP2: ${tp2_price:,.0f} ({tp2_percent}%)")
    if tp3_price:
        tp_summary.append(f"TP3: ${tp3_price:,.0f} ({tp3_percent}%)")
    
    return {
        "success": True,
        "position_id": position_id,
        "symbol": symbol,
        "direction": direction,
        "margin": margin,
        "entry_price": entry_price,
        "quantity": quantity,
        "stop_loss": stop_loss,
        "take_profit_levels": tp_summary if tp_summary else None,
        "fee": fee,
        "remaining_balance": new_balance
    }



def close_position(position_id: int, reason: str = "manual", user_id: str = None) -> dict:
    """
    Close an open position. Admin only.
    
    Args:
        position_id: ID of the position to close
        reason: Reason for closing (manual, stop_loss, take_profit, liquidated)
        user_id: User ID for permission check
    
    Returns:
        dict with close details or error
    """
    conn = get_db()
    
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM positions WHERE id = %s AND status = 'OPEN'", (position_id,))
        pos = cursor.fetchone()
        if not pos:
            conn.close()
            return {"error": f"Position {position_id} not found or already closed"}
        
        # Get current price
        close_price = get_current_price(pos["symbol"])
        if close_price <= 0:
            conn.close()
            return {"error": f"Failed to get price for {pos['symbol']}"}
        
        # Calculate PnL
        if pos["direction"] == "LONG":
            pnl = pos["quantity"] * (close_price - pos["entry_price"])
        else:
            pnl = pos["quantity"] * (pos["entry_price"] - close_price)
        
        # Close fee (0.05% of notional value, same as open)
        fee = pos["notional_value"] * 0.0005
        realized_pnl = pnl - fee
        
        # Determine status
        status = "CLOSED"
        if reason == "liquidated":
            status = "LIQUIDATED"
        
        # Update position
        cursor.execute("""
            UPDATE positions 
            SET status = %s, closed_at = CURRENT_TIMESTAMP, close_price = %s, realized_pnl = %s
            WHERE id = %s
        """, (status, close_price, realized_pnl, position_id))
        
        # Insert close order - 完整记录平仓信息
        cursor.execute("""
            INSERT INTO orders (position_id, symbol, action, direction, quantity, margin, entry_price, realized_pnl, close_reason, fee)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (position_id, pos["symbol"], "CLOSE", pos["direction"], pos["quantity"], pos["margin"], close_price, realized_pnl, reason, fee))
        
        # Update wallet for the position's owner (使用原子操作防止并发问题)
        position_user_id = pos["user_id"]
        
        # Atomic update: directly use SQL arithmetic instead of read-modify-write
        cursor.execute("""
            UPDATE virtual_wallet 
            SET current_balance = current_balance + %s + %s,
                total_pnl = total_pnl + %s,
                total_trades = total_trades + 1,
                win_trades = win_trades + %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
        """, (pos["margin"], realized_pnl, realized_pnl, 1 if realized_pnl > 0 else 0, position_user_id))
        
        conn.commit()
        
        # Get updated balance for return value
        cursor.execute("SELECT current_balance FROM virtual_wallet WHERE user_id = %s", (position_user_id,))
        wallet = cursor.fetchone()
        new_balance = wallet["current_balance"] if wallet else 0
    conn.close()
    
    return {
        "success": True,
        "position_id": position_id,
        "symbol": pos["symbol"],
        "direction": pos["direction"],
        "entry_price": pos["entry_price"],
        "close_price": close_price,
        "realized_pnl": round(realized_pnl, 2),
        "roi": round(realized_pnl / pos["margin"] * 100, 2),
        "reason": reason,
        "new_balance": round(new_balance, 2)
    }


def partial_close_position(
    position_id: int, 
    close_percent: float,
    move_sl_to_entry: bool = False,
    new_stop_loss: float = None,
    new_take_profit: float = None,
    reason: str = "partial_take_profit"
) -> dict:
    """
    Partially close a position (分批止盈).
    
    Example workflow:
    1. Open LONG ETH at $3000, qty=10
    2. Price hits $3300: partial_close(close_percent=80) → close 8 ETH, keep 2
    3. Move SL to entry: move_sl_to_entry=True → SL=$3000 (breakeven)
    4. Price hits $3500: partial_close(close_percent=80) → close 1.6 ETH, keep 0.4
    5. Continue until position fully closed or stopped out at breakeven
    
    Args:
        position_id: ID of the position
        close_percent: Percentage of REMAINING position to close (1-100)
        move_sl_to_entry: If True, move stop loss to entry price (breakeven)
        new_stop_loss: New stop loss price (optional, overrides move_sl_to_entry)
        new_take_profit: New take profit target (optional)
        reason: Reason for partial close
    
    Returns:
        dict with partial close details
    """
    if close_percent <= 0 or close_percent > 100:
        return {"error": "close_percent must be between 1 and 100"}
    
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM positions WHERE id = %s AND status = 'OPEN'", (position_id,))
        pos = cursor.fetchone()
        if not pos:
            conn.close()
            return {"error": f"Position {position_id} not found or already closed"}
        
        # Calculate remaining quantity (total - already closed)
        closed_qty = pos["closed_quantity"] if pos["closed_quantity"] else 0
        remaining_qty = pos["quantity"] - closed_qty
        
        if remaining_qty <= 0:
            conn.close()
            return {"error": "No remaining quantity to close"}
        
        # Calculate quantity to close
        close_qty = remaining_qty * (close_percent / 100)
        new_closed_qty = closed_qty + close_qty
        
        # Get current price
        close_price = get_current_price(pos["symbol"])
        if close_price <= 0:
            conn.close()
            return {"error": f"Failed to get price for {pos['symbol']}"}
        
        # Calculate PnL for this partial close
        if pos["direction"] == "LONG":
            pnl = close_qty * (close_price - pos["entry_price"])
        else:
            pnl = close_qty * (pos["entry_price"] - close_price)
        
        # Calculate proportional margin to release
        close_ratio = close_qty / pos["quantity"]
        margin_to_release = pos["margin"] * close_ratio
        
        # Fee (0.05% of closed notional)
        closed_notional = close_qty * close_price
        fee = closed_notional * 0.0005
        realized_pnl = pnl - fee
        
        # Determine new SL
        final_sl = pos["stop_loss"]
        if new_stop_loss is not None:
            final_sl = new_stop_loss
        elif move_sl_to_entry:
            final_sl = pos["entry_price"]  # Move to breakeven
        
        final_tp = new_take_profit if new_take_profit is not None else pos["take_profit"]
        
        # Check if position is now fully closed
        new_remaining = remaining_qty - close_qty
        is_fully_closed = new_remaining < 0.0001  # Tiny threshold for float precision
        
        if is_fully_closed:
            # Fully close the position
            cursor.execute("""
                UPDATE positions 
                SET status = 'CLOSED', closed_at = CURRENT_TIMESTAMP, 
                    close_price = %s, realized_pnl = COALESCE(realized_pnl, 0) + %s,
                    closed_quantity = quantity
                WHERE id = %s
            """, (close_price, realized_pnl, position_id))
        else:
            # Update position with new closed_quantity, reduced margin, and SL/TP
            # 关键修复：同步减少仓位的 margin，避免 equity 计算时保证金被重复计算
            new_margin = pos["margin"] - margin_to_release
            cursor.execute("""
                UPDATE positions 
                SET closed_quantity = %s, margin = %s, stop_loss = %s, take_profit = %s,
                    realized_pnl = COALESCE(realized_pnl, 0) + %s
                WHERE id = %s
            """, (new_closed_qty, new_margin, final_sl, final_tp, realized_pnl, position_id))
        
        # Insert partial close order record - 完整记录阶段性平仓信息
        cursor.execute("""
            INSERT INTO orders (position_id, symbol, action, direction, quantity, margin, entry_price, realized_pnl, fee)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (position_id, pos["symbol"], f"PARTIAL_CLOSE_{int(close_percent)}%", 
              pos["direction"], close_qty, margin_to_release, close_price, realized_pnl, fee))
        
        # Update wallet - release proportional margin + add realized PnL
        position_user_id = pos["user_id"]
        
        # When fully closed, also update trade statistics
        if is_fully_closed:
            # Get total realized PnL for this position (including previous partial closes)
            total_position_pnl = (pos["realized_pnl"] or 0) + realized_pnl
            cursor.execute("""
                UPDATE virtual_wallet 
                SET current_balance = current_balance + %s + %s,
                    total_pnl = total_pnl + %s,
                    total_trades = total_trades + 1,
                    win_trades = win_trades + %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
            """, (margin_to_release, realized_pnl, realized_pnl, 1 if total_position_pnl > 0 else 0, position_user_id))
        else:
            cursor.execute("""
                UPDATE virtual_wallet 
                SET current_balance = current_balance + %s + %s,
                    total_pnl = total_pnl + %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
            """, (margin_to_release, realized_pnl, realized_pnl, position_user_id))
        
        conn.commit()
        
        # Get updated balance
        cursor.execute("SELECT current_balance FROM virtual_wallet WHERE user_id = %s", (position_user_id,))
        wallet = cursor.fetchone()
    conn.close()
    
    return {
        "success": True,
        "position_id": position_id,
        "symbol": pos["symbol"],
        "direction": pos["direction"],
        "closed_percent": close_percent,
        "closed_quantity": round(close_qty, 6),
        "remaining_quantity": round(new_remaining, 6),
        "close_price": round(close_price, 2),
        "realized_pnl": round(realized_pnl, 2),
        "new_stop_loss": final_sl,
        "new_take_profit": final_tp,
        "is_fully_closed": is_fully_closed,
        "new_balance": round(wallet["current_balance"], 2) if wallet else 0
    }


def get_positions_summary(user_id: str = None) -> dict:
    """
    Get summary of current positions and wallet for trading decisions.
    Everyone sees the demo account (Admin's positions).
    
    Args:
        user_id: User ID (ignored - always uses Admin account for demo)
    
    Returns:
        dict with wallet and position info
    """
    # 演示模式：所有人都看Admin的仓位
    from tools.trading_tools import STRATEGY_ADMIN_USER_ID
    effective_user = STRATEGY_ADMIN_USER_ID  # 固定使用Admin账户
    
    conn = get_db()
    
    with conn.cursor() as cursor:
        # 查询Admin账户的钱包和持仓
        cursor.execute("SELECT * FROM virtual_wallet WHERE user_id = %s", (effective_user,))
        wallet = cursor.fetchone()
        
        if not wallet:
            # Create wallet for admin with initial balance
            cursor.execute("INSERT INTO virtual_wallet (user_id, initial_balance, current_balance) VALUES (%s, 10000, 10000)", (effective_user,))
            conn.commit()
            cursor.execute("SELECT * FROM virtual_wallet WHERE user_id = %s", (effective_user,))
            wallet = cursor.fetchone()
        
        cursor.execute(
            "SELECT * FROM positions WHERE user_id = %s AND status = 'OPEN' ORDER BY opened_at DESC",
            (effective_user,)
        )
        positions = cursor.fetchall()
    
    conn.close()
    
    # Calculate margins and unrealized PnL
    open_positions = []
    total_unrealized_pnl = 0
    total_margin_in_use = 0
    
    for pos in positions:
        current_price = get_current_price(pos["symbol"])
        total_margin_in_use += pos["margin"]
        
        # 计算剩余数量（考虑阶段性平仓）
        closed_qty = pos["closed_quantity"] if pos["closed_quantity"] else 0
        remaining_qty = pos["quantity"] - closed_qty
        
        # 基于剩余数量计算未实现盈亏
        if pos["direction"] == "LONG":
            unrealized_pnl = remaining_qty * (current_price - pos["entry_price"])
        else:
            unrealized_pnl = remaining_qty * (pos["entry_price"] - current_price)
        
        roi = unrealized_pnl / pos["margin"] * 100 if pos["margin"] > 0 else 0
        total_unrealized_pnl += unrealized_pnl
        
        # Build take profit levels info
        tp_levels = []
        if pos["tp1_price"]:
            status = "✅" if pos["tp1_triggered"] else "⏳"
            tp_levels.append(f"{status} TP1: ${pos['tp1_price']:,.0f} ({pos['tp1_percent']}%)")
        if pos["tp2_price"]:
            status = "✅" if pos["tp2_triggered"] else "⏳"
            tp_levels.append(f"{status} TP2: ${pos['tp2_price']:,.0f} ({pos['tp2_percent']}%)")
        if pos["tp3_price"]:
            status = "✅" if pos["tp3_triggered"] else "⏳"
            tp_levels.append(f"{status} TP3: ${pos['tp3_price']:,.0f} ({pos['tp3_percent']}%)")
        
        open_positions.append({
            "id": pos["id"],
            "symbol": pos["symbol"],
            "direction": pos["direction"],
            "margin": pos["margin"],
            "entry_price": pos["entry_price"],
            "current_price": current_price,
            "unrealized_pnl": round(unrealized_pnl, 2),
            "roi_percent": round(roi, 2),
            "stop_loss": pos["stop_loss"],
            "take_profit_levels": tp_levels if tp_levels else None,
            "tp1_triggered": bool(pos["tp1_triggered"]),
            "opened_at": pos["opened_at"]
        })
    
    # Calculate equity = available + margin_in_use + unrealized_pnl
    available = wallet["current_balance"]
    equity = available + total_margin_in_use + total_unrealized_pnl
    
    return {
        "available_balance": round(available, 2),  # Can use directly for new trades
        "margin_in_use": round(total_margin_in_use, 2),  # Already locked in positions
        "unrealized_pnl": round(total_unrealized_pnl, 2),
        "equity": round(equity, 2),  # Total account value
        "total_realized_pnl": round(wallet["total_pnl"], 2),
        "total_trades": wallet["total_trades"],
        "win_rate": round(wallet["win_trades"] / wallet["total_trades"] * 100, 1) if wallet["total_trades"] > 0 else 0,
        "open_positions": open_positions,
        "position_count": len(open_positions)
    }



def update_stop_loss_take_profit(position_id: int, new_sl: float = None, new_tp: float = None, user_id: str = None) -> dict:
    """
    Update stop loss and/or take profit for a position. Admin only.
    
    Args:
        position_id: ID of the position
        new_sl: New stop loss price (None to keep current)
        new_tp: New take profit price (None to keep current)
        user_id: User ID for permission check
    
    Returns:
        dict with update status
    """
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM positions WHERE id = %s AND status = 'OPEN'", (position_id,))
        pos = cursor.fetchone()
        if not pos:
            conn.close()
            return {"error": f"Position {position_id} not found or already closed"}
        
        updates = []
        params = []
        
        if new_sl is not None:
            updates.append("stop_loss = %s")
            params.append(new_sl)
        
        if new_tp is not None:
            updates.append("take_profit = %s")
            params.append(new_tp)
        
        if not updates:
            conn.close()
            return {"error": "No updates provided"}
        
        params.append(position_id)
        cursor.execute(f"UPDATE positions SET {', '.join(updates)} WHERE id = %s", tuple(params))
        
        # Log the modification
        cursor.execute("""
            INSERT INTO orders (position_id, symbol, action, stop_loss, take_profit)
            VALUES (%s, %s, 'MODIFY_SL_TP', %s, %s)
        """, (position_id, pos["symbol"], new_sl, new_tp))
        
        conn.commit()
    conn.close()
    
    return {
        "success": True,
        "position_id": position_id,
        "symbol": pos["symbol"],
        "new_stop_loss": new_sl,
        "new_take_profit": new_tp
    }


# ==========================================
# Price Alert Tools
# ==========================================

def set_price_alert(
    symbol: str,
    trigger_price: float,
    condition: str,
    strategy_context: str = None
) -> dict:
    """
    设置价格警报。当价格达到触发条件时，系统会自动调用Agent重新分析。
    
    使用场景：
    - 等待价格回调到支撑位再开仓
    - 等待价格突破阻力位确认后开仓
    - 监控关键价位的市场反应
    
    Args:
        symbol: 币种符号 (BTC, ETH, SOL)
        trigger_price: 触发价格
        condition: 触发条件
            - "above": 价格突破到 trigger_price 以上时触发
            - "below": 价格跌破到 trigger_price 以下时触发
        strategy_context: 策略上下文说明，触发时会作为提示传递给Agent
            例如: "BTC在100000被拒绝，价格跌回99000时验证是否形成双顶，若确认则开空"
    
    Returns:
        dict with alert details or error
    
    Example:
        set_price_alert(
            symbol="BTC",
            trigger_price=99000,
            condition="below",
            strategy_context="等待BTC从100000回落到99000，验证是否在100000形成有效阻力后开空"
        )
    """
    from price_alerts import create_alert, get_alerts_by_symbol
    
    symbol = symbol.upper()
    condition = condition.lower()
    
    if condition not in ["above", "below"]:
        return {"error": "condition 必须是 'above' 或 'below'"}
    
    if trigger_price <= 0:
        return {"error": "trigger_price 必须大于0"}
    
    # 获取当前价格
    current_price = get_current_price(symbol)
    if current_price <= 0:
        return {"error": f"无法获取 {symbol} 当前价格"}
    
    # 验证条件逻辑
    if condition == "above" and current_price >= trigger_price:
        return {"error": f"当前价格 ${current_price:,.0f} 已经高于触发价 ${trigger_price:,.0f}，无需设置 above 警报"}
    
    if condition == "below" and current_price <= trigger_price:
        return {"error": f"当前价格 ${current_price:,.0f} 已经低于触发价 ${trigger_price:,.0f}，无需设置 below 警报"}

    # 安全缓冲：防止设置过于紧贴当前价格的警报导致死循环触发
    distance = abs(current_price - trigger_price)
    distance_pct = distance / current_price * 100
    MIN_DISTANCE_PCT = 0.2  # 0.2% 最小距离

    if distance_pct < MIN_DISTANCE_PCT:
         return {"error": f"警报价格距离当前价格过近 ({distance_pct:.2f}% < {MIN_DISTANCE_PCT}%)，请设置更有意义的支撑/阻力位，防止频繁误触"}
    
    # 检查是否已有相同警报
    existing = get_alerts_by_symbol(symbol)
    for alert in existing:
        if abs(alert["trigger_price"] - trigger_price) < 10:  # 价格相近（<$10差异）
            return {"error": f"已存在相似警报 (ID:{alert['id']}): {symbol} {alert['trigger_condition']} ${alert['trigger_price']:,.0f}"}
    
    # 创建警报
    alert_id = create_alert(
        symbol=symbol,
        trigger_price=trigger_price,
        trigger_condition=condition,
        strategy_context=strategy_context
    )
    
    condition_text = "突破" if condition == "above" else "跌破"
    distance = abs(current_price - trigger_price)
    distance_pct = distance / current_price * 100
    
    return {
        "success": True,
        "alert_id": alert_id,
        "symbol": symbol,
        "trigger_price": trigger_price,
        "condition": condition,
        "current_price": current_price,
        "distance": f"${distance:,.0f} ({distance_pct:.1f}%)",
        "message": f"警报已设置：当 {symbol} {condition_text} ${trigger_price:,.0f} 时触发分析"
    }


def get_price_alerts(symbol: str = None) -> dict:
    """
    查看当前待触发的价格警报。
    
    Args:
        symbol: 可选，指定币种筛选，不填则返回所有
    
    Returns:
        dict with pending alerts
    """
    from price_alerts import get_pending_alerts, get_alerts_by_symbol
    
    if symbol:
        alerts = get_alerts_by_symbol(symbol.upper())
    else:
        alerts = get_pending_alerts()
    
    if not alerts:
        return {
            "count": 0,
            "alerts": [],
            "message": "当前没有待触发的价格警报"
        }
    
    formatted_alerts = []
    for alert in alerts:
        condition_text = "突破" if alert["trigger_condition"] == "above" else "跌破"
        current_price = get_current_price(alert["symbol"])
        distance = abs(current_price - alert["trigger_price"])
        distance_pct = distance / current_price * 100 if current_price > 0 else 0
        
        # 压缩输出：只保留关键信息
        formatted_alerts.append({
            "id": alert["id"],
            "symbol": alert["symbol"],
            "condition": f"{condition_text} ${alert['trigger_price']:,.0f}",
            "dist_pct": f"{distance_pct:.1f}%",
            "strategy": alert["strategy_context"][:50] + "..." if alert["strategy_context"] and len(alert["strategy_context"]) > 50 else alert["strategy_context"]
        })
    
    return {
        "count": len(formatted_alerts),
        "alerts": formatted_alerts
    }


def cancel_price_alert(alert_id: int = None, symbol: str = None) -> dict:
    """
    取消价格警报。
    
    Args:
        alert_id: 要取消的警报ID（优先）
        symbol: 取消该币种的所有警报（如果未指定alert_id）
    
    Returns:
        dict with cancellation result
    """
    from price_alerts import cancel_alert, cancel_alerts_by_symbol
    
    if alert_id:
        success = cancel_alert(alert_id)
        if success:
            return {"success": True, "message": f"警报 {alert_id} 已取消"}
        else:
            return {"error": f"警报 {alert_id} 不存在或已触发/取消"}
    
    if symbol:
        count = cancel_alerts_by_symbol(symbol.upper())
        return {"success": True, "message": f"已取消 {symbol} 的 {count} 个警报"}
    
    return {"error": "请指定 alert_id 或 symbol"}

