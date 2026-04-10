"""
Strategy Scheduler - Automated 4-hour strategy trigger

Run as independent process: python scheduler.py
Or integrate with main.py for API-controlled start/stop
"""
import schedule
import time
import sqlite3
import json
from datetime import datetime
import requests
import os
import threading

# Configuration - use environment variable for API URL
AGENT_API_URL = os.getenv("AGENT_API_URL", "http://localhost:8000")
DB_PATH = os.getenv("DB_PATH", "tmp/test.db")

# Use admin user ID for all scheduler operations
from tools.trading_tools import STRATEGY_ADMIN_USER_ID, set_current_user
SCHEDULER_USER_ID = STRATEGY_ADMIN_USER_ID  # Scheduler runs as admin

# ============= Scheduler State Management =============
_scheduler_running = False
_scheduler_thread = None
_scheduler_lock = threading.Lock()
_scheduler_lock_file = None

def is_scheduler_running() -> bool:
    """Return current scheduler running status"""
    return _scheduler_running

def get_scheduler_status() -> dict:
    """Get detailed scheduler status"""
    return {
        "running": _scheduler_running,
        "admin_user_id": SCHEDULER_USER_ID
    }

def start_scheduler() -> dict:
    """Start the scheduler in background thread"""
    global _scheduler_running, _scheduler_thread, _scheduler_lock_file
    
    with _scheduler_lock:
        if _scheduler_running:
            return {"success": False, "message": "Scheduler already running"}
            
        # Try to acquire file lock to prevent multi-process duplicates
        try:
            import fcntl
            lock_path = "/tmp/scheduler.lock"
            _scheduler_lock_file = open(lock_path, "w")
            try:
                # Try non-blocking exclusive lock
                fcntl.flock(_scheduler_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                _scheduler_lock_file.close()
                _scheduler_lock_file = None
                print("[Scheduler] Another instance is running (lock held). Skipping start.")
                return {"success": False, "message": "Scheduler locked by another process"}
        except ImportError:
            pass # Windows or non-Unix, skip lock

        _scheduler_running = True
        _scheduler_thread = threading.Thread(target=_run_scheduler_loop, daemon=True)
        _scheduler_thread.start()
        print("[Scheduler] Started via API")
        return {"success": True, "message": "Scheduler started"}

def stop_scheduler() -> dict:
    """Stop the scheduler"""
    global _scheduler_running
    
    with _scheduler_lock:
        if not _scheduler_running:
            return {"success": False, "message": "Scheduler not running"}
        
        _scheduler_running = False
        schedule.clear()  # Clear all scheduled jobs
        print("[Scheduler] Stopped via API")
        return {"success": True, "message": "Scheduler stopped"}

def _run_scheduler_loop():
    """Internal scheduler loop - runs until stopped (Strategy tasks only)"""
    global _scheduler_running
    
    # 清除所有旧任务，防止重复注册
    schedule.clear()
    
    print("[Scheduler] Starting Strategy Nexus Scheduler...")
    print("[Scheduler] Strategy checks EVERY MINUTE (individual per-user intervals)")
    print("[Scheduler] Position monitor runs every 10 seconds")
    print("[Scheduler] Binance position sync runs every 30 seconds")
    # Schedule strategy EVERY MINUTE (checks user-specific intervals)
    schedule.every(1).minutes.do(trigger_strategy)
    
    # Schedule position price updates every 10 seconds (for virtual trading)
    schedule.every(10).seconds.do(update_positions_prices)
    
    # Schedule Binance position sync every 30 seconds (for real trading users)
    schedule.every(30).seconds.do(sync_binance_users_positions)
    
    # Schedule orphan order cleanup every 5 minutes (清理无仓位的孤儿止盈止损挂单)
    schedule.every(5).minutes.do(cleanup_orphan_orders)
    
    # Run position update immediately
    update_positions_prices()
    
    print("[Scheduler] Scheduler is running. Use API to stop.")
    
    while _scheduler_running:
        try:
            schedule.run_pending()
        except Exception as e:
            print(f"[Scheduler] CRITICAL ERROR in run_pending: {e}")
            import traceback
            traceback.print_exc()
        time.sleep(1)
    
    print("[Scheduler] Scheduler loop exited")


# ============= Binance Multi-User Position Sync =============


def sync_binance_users_positions():
    """
    Sync positions for all users who have enabled Binance trading.
    
    This function:
    1. Gets all users with trading enabled
    2. For each user, syncs their Binance positions
    3. Logs any position changes or errors
    
    Note: SL/TP orders are handled by Binance server-side,
    so we only need to sync position status changes.
    """
    try:
        from binance_client import get_all_active_trading_users
        from tools.binance_trading_tools import binance_get_positions_summary
        
        # Get all users with trading enabled
        users = get_all_active_trading_users()
        
        if not users:
            return
        
        # print(f"[Scheduler] Syncing Binance positions for {len(users)} user(s)...")
        
        for user_id in users:
            try:
                # 1. Sync Positions (Status)
                summary = binance_get_positions_summary(user_id)
                if "error" in summary:
                    print(f"[Scheduler] Error syncing positions for {user_id[:8]}: {summary['error']}")
                
                # 2. Sync Stats (PnL/WinRate) via Incremental Trade History
                sync_user_account_stats(user_id)
                    
            except Exception as e:
                print(f"[Scheduler] Error syncing user {user_id[:8]}: {e}")
        
    except ImportError as e:
        # Module not available, skip silently
        pass
    except Exception as e:
        print(f"[Scheduler] Error in Binance sync: {e}")


def sync_user_account_stats(user_id: str):
    """
    Incrementally sync user trade history to update PnL and Win Rate stats.
    Compatible with Binance API restrictions (per symbol, fromId).
    
    Supports both legacy (get_user_binance_client) and new Workspace 
    (exchange_accounts via _get_trading_client) systems.
    """
    from app.database import get_db_connection
    
    # 尝试获取 client：先旧系统，再新系统
    client = None
    
    # 路径 A: 旧系统
    from binance_client import get_user_binance_client
    client = get_user_binance_client(user_id)
    
    # 路径 B: 新系统 Workspace
    if not client:
        try:
            from tools.binance_trading_tools import _get_trading_client
            client, err = _get_trading_client(user_id, require_trading_enabled=False)
            if err:
                # print(f"[Stats] No client available for {user_id[:8]}: {err}")
                return
        except Exception as e:
            # print(f"[Stats] _get_trading_client error: {e}")
            return
    
    if not client:
        return

    # List of symbols to track (Top coins + others as needed)
    SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT"]
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            for symbol in SYMBOLS:
                # 1. Get last synced ID
                cursor.execute(
                    "SELECT last_trade_id FROM binance_sync_state WHERE user_id = %s AND symbol = %s",
                    (user_id, symbol)
                )
                row = cursor.fetchone()
                last_id = row[0] if row else 0
                
                # 2. Fetch new trades (use fromId if we have history, otherwise recent)
                # Note: If last_id is 0, we might want to fetch recent history (e.g. last 1000 trades)
                # But to avoid massive initial sync time for active accounts, let's limit to recent if 0.
                try:
                    # fromId + 1 to avoid re-processing the same trade
                    params = {"limit": 500}
                    if last_id > 0:
                        params["fromId"] = last_id + 1
                    
                    trades = client.get_trade_history(symbol=symbol, **params)
                    
                    if not trades or not isinstance(trades, list):
                        continue
                        
                    # 3. Process new trades
                    new_pnl = 0.0
                    new_trades_count = 0
                    new_win_trades = 0
                    max_id = last_id
                    
                    for trade in trades:
                        # Update max_id
                        t_id = int(trade.get("id", 0))
                        if t_id > max_id:
                            max_id = t_id
                            
                        # Only count TRADES that have Realized PnL (Close positions)
                        # Binance puts realizedPnl on closing trades
                        r_pnl = float(trade.get("realizedPnl", 0))
                        
                        if r_pnl != 0:
                            new_pnl += r_pnl
                            new_trades_count += 1
                            if r_pnl > 0:
                                new_win_trades += 1
                    
                    # 4. Update DB if we found new data
                    if max_id > last_id:
                        cursor.execute("""
                            INSERT INTO binance_sync_state (user_id, symbol, last_trade_id, total_pnl, total_trades, win_trades, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, NOW())
                            ON CONFLICT (user_id, symbol) DO UPDATE SET
                            last_trade_id = EXCLUDED.last_trade_id,
                            total_pnl = binance_sync_state.total_pnl + EXCLUDED.total_pnl,
                            total_trades = binance_sync_state.total_trades + EXCLUDED.total_trades,
                            win_trades = binance_sync_state.win_trades + EXCLUDED.win_trades,
                            updated_at = NOW()
                        """, (user_id, symbol, max_id, new_pnl, new_trades_count, new_win_trades))
                        
                        # print(f"[Stats] Updated {symbol} for {user_id[:8]}: +{new_trades_count} trades, PnL: {new_pnl:.2f}")
                        
                except Exception as e:
                    # print(f"[Stats] Sync error for {symbol}: {e}")
                    pass
            
            conn.commit()
    finally:
        conn.close()


import os
import time
import uuid
import json
import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from app.database import get_db_connection as get_db

# ... existing imports ...

# DB_PATH removed

# get_db replaced by import

def log_strategy_round(round_id: str, symbols: str, response: dict, user_id: str = None, trader_instance_id: str = None):
    """Save strategy log to database"""
    try:
        conn = get_db()
        
        # Extract structured content from response
        raw_response = response.get("content", "")
        
        # Parse sections from response
        market_analysis = ""
        position_check = ""
        strategy_decision = ""
        actions_taken = "[]"
        
        if "### Market Analysis" in raw_response:
            parts = raw_response.split("### Market Analysis")
            if len(parts) > 1:
                market_analysis = parts[1].split("###")[0].strip()[:2000]
        
        if "### Position Health Check" in raw_response:
            parts = raw_response.split("### Position Health Check")
            if len(parts) > 1:
                position_check = parts[1].split("###")[0].strip()[:1000]
        
        if "### Strategy Decision" in raw_response:
            parts = raw_response.split("### Strategy Decision")
            if len(parts) > 1:
                strategy_decision = parts[1].strip()[:1000]
        
        # Check if Agent already logged this round within last 3 minutes (to avoid duplicates)
        # Agent may log with a slightly different round_id (1-2 min later)
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 1 FROM strategy_logs 
                WHERE symbols = %s 
                AND timestamp::timestamptz > NOW() - INTERVAL '3 minutes'
            """, (symbols,))
            existing = cursor.fetchone()
            
            if existing:
                conn.close()
                print(f"[Scheduler] Recent log for {symbols} exists, skipping duplicate")
                return
            
            cursor.execute("""
                INSERT INTO strategy_logs (round_id, symbols, market_analysis, position_check, strategy_decision, actions_taken, raw_response, "timestamp", user_id, trader_instance_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s)
            """, (round_id, symbols, market_analysis, position_check, strategy_decision, actions_taken, raw_response[:5000], user_id, trader_instance_id))
            
            conn.commit()
        conn.close()
        print(f"[Scheduler] Logged strategy round: {round_id}")
    except Exception as e:
        print(f"[Scheduler] Error logging strategy: {e}")

# Retry logic removed as it was specific to SQLite locking


def update_positions_prices():
    """Update current prices and check SL/TP for all open positions.
    
    分批止盈逻辑:
    - TP1 触发: 平仓 tp1_percent，自动移止损到开仓价保本
    - TP2 触发: 平仓 tp2_percent (相对于原始仓位)
    - TP3 触发: 平掉余仓
    """
    positions_to_close = []  # Collect positions to fully close
    partial_close_actions = []  # Collect partial close actions
    
    try:
        conn = get_db()
        with conn.cursor() as cursor:
            # Only process admin's positions (filter by user_id)
            cursor.execute("SELECT * FROM positions WHERE status = 'OPEN' AND user_id = %s", (SCHEDULER_USER_ID,))
            positions = cursor.fetchall()
            
            for pos in positions:
                symbol = pos["symbol"]
                
                # Get current price
                try:
                    import os
                    binance_base = os.getenv("BINANCE_API_BASE", "https://api.binance.com")
                    resp = requests.get(f"{binance_base}/api/v3/ticker/price?symbol={symbol}USDT", timeout=5)
                    current_price = float(resp.json().get("price", 0))
                except:
                    continue
                
                if current_price <= 0:
                    continue
                
                # 计算剩余数量（考虑阶段性平仓）
                closed_qty = pos["closed_quantity"] if pos["closed_quantity"] else 0
                remaining_qty = pos["quantity"] - closed_qty
                
                # Calculate unrealized PnL (基于剩余数量)
                if pos["direction"] == "LONG":
                    unrealized_pnl = remaining_qty * (current_price - pos["entry_price"])
                else:
                    unrealized_pnl = remaining_qty * (pos["entry_price"] - current_price)
                
                # Update position price
                cursor.execute("""
                    UPDATE positions SET current_price = %s, unrealized_pnl = %s WHERE id = %s
                """, (current_price, unrealized_pnl, pos["id"]))
                
                # Check liquidation (unrealized_pnl <= -margin)
                if unrealized_pnl <= -pos["margin"]:
                    print(f"[Scheduler] LIQUIDATION triggered for position {pos['id']} ({symbol} {pos['direction']})")
                    positions_to_close.append((pos["id"], "liquidated"))
                    continue
                
                # Check stop loss
                if pos["stop_loss"]:
                    if (pos["direction"] == "LONG" and current_price <= pos["stop_loss"]) or \
                       (pos["direction"] == "SHORT" and current_price >= pos["stop_loss"]):
                        print(f"[Scheduler] STOP LOSS triggered for position {pos['id']} ({symbol})")
                        positions_to_close.append((pos["id"], "stop_loss"))
                        continue
                
                # ========== 分批止盈检查 ==========
                is_long = pos["direction"] == "LONG"
                
                def price_hit(target_price):
                    """Check if price hit target for this direction"""
                    if is_long:
                        return current_price >= target_price
                    else:
                        return current_price <= target_price
                
                # Check TP1 (if not yet triggered)
                if pos["tp1_price"] and not pos["tp1_triggered"]:
                    if price_hit(pos["tp1_price"]):
                        tp1_pct = pos["tp1_percent"] or 50
                        print(f"[Scheduler] TP1 triggered for position {pos['id']} ({symbol}) - closing {tp1_pct}%, moving SL to entry")
                        partial_close_actions.append({
                            "position_id": pos["id"],
                            "close_percent": tp1_pct,
                            "move_sl_to_entry": True,  # 保本铁律
                            "tp_level": 1
                        })
                        continue  # Don't check further TPs this cycle
                
                # Check TP2 (only if TP1 already triggered)
                elif pos["tp2_price"] and pos["tp1_triggered"] and not pos["tp2_triggered"]:
                    if price_hit(pos["tp2_price"]):
                        # Calculate percentage of remaining position
                        # If original was 100 and TP1 closed 50%, now we have 50%
                        # To close TP2's 30% of original, we close 60% of remaining (30/50=60%)
                        tp1_pct = pos["tp1_percent"] or 50
                        tp2_pct = pos["tp2_percent"] or 30
                        remaining_pct = 100 - tp1_pct
                        close_pct_of_remaining = (tp2_pct / remaining_pct) * 100 if remaining_pct > 0 else 100
                        print(f"[Scheduler] TP2 triggered for position {pos['id']} ({symbol}) - closing {close_pct_of_remaining:.0f}% of remaining")
                        partial_close_actions.append({
                            "position_id": pos["id"],
                            "close_percent": min(close_pct_of_remaining, 100),
                            "move_sl_to_entry": False,
                            "tp_level": 2
                        })
                        continue
                
                # Check TP3 (only if TP2 already triggered)
                elif pos["tp3_price"] and pos["tp2_triggered"] and not pos["tp3_triggered"]:
                    if price_hit(pos["tp3_price"]):
                        print(f"[Scheduler] TP3 triggered for position {pos['id']} ({symbol}) - closing remaining position")
                        positions_to_close.append((pos["id"], "take_profit"))
                        continue
            
            conn.commit()
        conn.close()
        
        # Execute partial closes AFTER releasing the connection
        if partial_close_actions:
            set_current_user(SCHEDULER_USER_ID)
            from tools.trading_tools import partial_close_position
            
            for action in partial_close_actions:
                try:
                    result = partial_close_position(
                        position_id=action["position_id"],
                        close_percent=action["close_percent"],
                        move_sl_to_entry=action["move_sl_to_entry"]
                    )
                    print(f"[Scheduler] Partial close result: {result}")
                    
                    # Mark TP level as triggered
                    conn2 = get_db()
                    with conn2.cursor() as cursor2:
                        tp_level = action["tp_level"]
                        cursor2.execute(f"UPDATE positions SET tp{tp_level}_triggered = 1 WHERE id = %s", (action["position_id"],))
                        conn2.commit()
                    conn2.close()
                    
                except Exception as e:
                    print(f"[Scheduler] Error partial closing position {action['position_id']}: {e}")
        
        # Execute full closes AFTER releasing the connection
        if positions_to_close:
            set_current_user(SCHEDULER_USER_ID)
            from tools.trading_tools import close_position
            for pos_id, reason in positions_to_close:
                try:
                    result = close_position(pos_id, reason=reason)
                    print(f"[Scheduler] Position {pos_id} closed: {result}")
                except Exception as e:
                    print(f"[Scheduler] Error closing position {pos_id}: {e}")
                    
    except Exception as e:
        print(f"[Scheduler] Error updating positions: {e}")
# 去重锁：防止同一分钟内重复触发
_last_strategy_trigger = None
_strategy_trigger_lock = threading.Lock()

def trigger_strategy():
    """
    Trigger agent strategy analysis for all RUNNING trader instances.
    
    核心改动 (2026-04-06):
    - 改为基于 trader_instances (status=RUNNING) 触发，而非 strategy_profiles (is_enabled=TRUE)
    - 这样用户在 UI 上停止 trader 后，策略真正停止执行
    - 每个 trader_instance 绑定了特定的 strategy_profile + llm_config + exchange_account
    """
    global _last_strategy_trigger
    round_id = datetime.now().strftime("%Y-%m-%d_%H:%M")
    
    # Skip if already run this minute
    with _strategy_trigger_lock:
        if _last_strategy_trigger == round_id:
            return
        _last_strategy_trigger = round_id
    
    print(f"\n[Scheduler] ========== Automated Strategy Round: {round_id} ==========")
    
    try:
        conn = get_db()
        with conn.cursor() as cursor:
            # 查询所有 RUNNING 状态的 trader_instances，JOIN 其绑定的 strategy_profile
            cursor.execute("""
                SELECT 
                    ti.id AS trader_instance_id,
                    ti.user_id,
                    ti.llm_config_id,
                    sp.id AS strategy_profile_id,
                    sp.symbols,
                    sp.timeframes,
                    sp.trading_interval,
                    sp.prompt_template,
                    sp.last_analyzed_at
                FROM trader_instances ti
                INNER JOIN strategy_profiles sp ON sp.id = ti.strategy_profile_id
                WHERE ti.status = 'RUNNING'
                  AND ti.is_enabled = TRUE
                  AND sp.is_enabled = TRUE
            """)
            active_traders = cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"[Scheduler] Database error: {e}")
        return

    print(f"[Scheduler] Found {len(active_traders)} running trader instance(s)")
    
    for idx, trader in enumerate(active_traders):
        user_id = trader["user_id"]
        interval_min = trader["trading_interval"] or 60
        last_analyzed = trader["last_analyzed_at"]
        
        should_run = False
        if not last_analyzed:
            should_run = True # Initial run
        else:
            # Calculate time difference
            time_diff = (datetime.now() - last_analyzed).total_seconds() / 60
            if time_diff >= (interval_min - 0.5): # 30s buffer
                should_run = True
        
        if not should_run:
            continue

        # Throttling to avoid API rate limits
        if idx > 0:
            time.sleep(2)
        
        _run_trader_instance(trader, round_id)


def _run_trader_instance(trader: dict, round_id: str):
    """Execution logic for a specific running trader instance."""
    user_id = trader["user_id"]
    trader_instance_id = trader["trader_instance_id"]
    profile_id = trader["strategy_profile_id"]
    symbols = trader["symbols"]
    prompt = trader["prompt_template"]
    
    print(f"[Scheduler] Executing Trader #{trader_instance_id} (Profile #{profile_id}) for User {user_id[:8]}... (Interval: {trader['trading_interval']}m)")
    
    try:
        # Build the individualized prompt - simplified since analysis framework is now
        # built into the Agent's System Prompt via L0 core instructions
        full_message = f"""执行策略扫描：{symbols}
分析周期：{trader.get('timeframes', '1h,4h')}
请按照标准分析流程执行，完成后记录日志。"""
        
        response = requests.post(
            f"{AGENT_API_URL}/agents/trading-strategy-agent/runs",
            data={
                "message": full_message,
                "user_id": user_id,
                "trader_instance_id": str(trader_instance_id),
                "session_id": f"auto-t{trader_instance_id}-{round_id.replace(':', '-')}",
                "stream": "False"
            },
            timeout=120
        )
        
        if response.status_code == 200:
            print(f"[Scheduler] Trader #{trader_instance_id} completed successfully")
            
            # Update last_analyzed_at on the strategy profile
            try:
                conn = get_db()
                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE strategy_profiles SET last_analyzed_at = %s WHERE id = %s",
                        (datetime.now(), profile_id)
                    )
                    conn.commit()
                conn.close()
            except Exception as db_e:
                print(f"[Scheduler] Failed to update last_analyzed_at for Profile #{profile_id}: {db_e}")
        else:
            print(f"[Scheduler] Error for Trader #{trader_instance_id}: {response.status_code} - {response.text[:200]}")
            log_strategy_round(round_id, symbols, {"content": f"Error: {response.status_code}"}, user_id=user_id, trader_instance_id=str(trader_instance_id))
            
    except Exception as e:
        print(f"[Scheduler] Exception executing Trader #{trader_instance_id}: {e}")
        log_strategy_round(round_id, symbols, {"content": f"Exception: {str(e)}"}, user_id=user_id, trader_instance_id=str(trader_instance_id))



# ============= Orphan Order Cleanup =============

def cleanup_orphan_orders():
    """
    定期扫描所有活跃交易用户，清理孤儿订单。
    
    孤儿订单 = 已经没有对应持仓的止损/止盈/条件挂单。
    这些订单通常是因为仓位被止损或止盈触发自动平仓后，
    另一侧的挂单没有被自动取消而遗留下来的。
    """
    try:
        from binance_client import get_all_active_trading_users
        from tools.binance_trading_tools import binance_cancel_orphan_orders
        
        users = get_all_active_trading_users()
        if not users:
            return
        
        for user_id in users:
            try:
                result = binance_cancel_orphan_orders(user_id=user_id)
                if result.get("error"):
                    print(f"[OrphanCleanup] Error for user {user_id[:8]}: {result['error']}")
                elif (result.get("cancelled_normal", 0) + result.get("cancelled_algo", 0)) > 0:
                    print(f"[OrphanCleanup] User {user_id[:8]}: cleaned {result['cancelled_normal']} normal + {result['cancelled_algo']} algo orphan orders")
            except Exception as e:
                print(f"[OrphanCleanup] Exception for user {user_id[:8]}: {e}")
    except ImportError:
        pass
    except Exception as e:
        print(f"[OrphanCleanup] Error: {e}")


def main():
    """Standalone scheduler entry point"""
    global _scheduler_running
    _scheduler_running = True
    try:
        _run_scheduler_loop()
    except KeyboardInterrupt:
        print("\n[Scheduler] Stopped by user")
        _scheduler_running = False

if __name__ == "__main__":
    main()
