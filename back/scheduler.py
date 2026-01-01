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
from trading_tools import STRATEGY_ADMIN_USER_ID, set_current_user
SCHEDULER_USER_ID = STRATEGY_ADMIN_USER_ID  # Scheduler runs as admin

# ============= Scheduler State Management =============
_scheduler_running = False
_scheduler_thread = None
_scheduler_lock = threading.Lock()

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
    global _scheduler_running, _scheduler_thread
    
    with _scheduler_lock:
        if _scheduler_running:
            return {"success": False, "message": "Scheduler already running"}
        
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
    
    print("[Scheduler] Starting Strategy Nexus Scheduler...")
    print("[Scheduler] Strategy triggers HOURLY at :30 (every hour)")
    print("[Scheduler] Position monitor runs every 10 seconds")
    print("[Scheduler] Price alert check runs every 60 seconds")
    print("[Scheduler] Note: Daily Report runs independently (not controlled here)")
    print()
    
    # Schedule strategy at fixed times (every 1 hour, at :30)
    for hour in range(24):
        time_str = f"{hour:02d}:30"
        schedule.every().day.at(time_str).do(trigger_strategy)
    
    # Schedule position price updates every 10 seconds
    schedule.every(10).seconds.do(update_positions_prices)
    
    # Schedule price alert checks every 60 seconds
    schedule.every(60).seconds.do(check_price_alerts)
    
    # NOTE: Daily Report is now scheduled independently in main.py
    # It runs automatically regardless of strategy scheduler status
    
    # Run position update immediately
    update_positions_prices()
    
    print("[Scheduler] Scheduler is running. Use API to stop.")
    
    while _scheduler_running:
        schedule.run_pending()
        time.sleep(1)
    
    print("[Scheduler] Scheduler loop exited")


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def log_strategy_round(round_id: str, symbols: str, response: dict):
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
        existing = conn.execute("""
            SELECT 1 FROM strategy_logs 
            WHERE symbols = ? 
            AND timestamp > datetime('now', '-3 minutes')
        """, (symbols,)).fetchone()
        if existing:
            conn.close()
            print(f"[Scheduler] Recent log for {symbols} exists, skipping duplicate")
            return
        
        conn.execute("""
            INSERT INTO strategy_logs (round_id, symbols, market_analysis, position_check, strategy_decision, actions_taken, raw_response)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (round_id, symbols, market_analysis, position_check, strategy_decision, actions_taken, raw_response[:5000]))
        
        conn.commit()
        conn.close()
        print(f"[Scheduler] Logged strategy round: {round_id}")
    except Exception as e:
        print(f"[Scheduler] Error logging strategy: {e}")

def update_positions_prices():
    """Update current prices and check SL/TP for all open positions"""
    positions_to_close = []  # Collect positions to close
    
    try:
        conn = get_db()
        # Only process admin's positions (filter by user_id)
        positions = conn.execute("SELECT * FROM positions WHERE status = 'OPEN' AND user_id = ?", (SCHEDULER_USER_ID,)).fetchall()
        
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
            
            # Calculate unrealized PnL
            if pos["direction"] == "LONG":
                unrealized_pnl = pos["quantity"] * (current_price - pos["entry_price"])
            else:
                unrealized_pnl = pos["quantity"] * (pos["entry_price"] - current_price)
            
            # Update position price
            conn.execute("""
                UPDATE positions SET current_price = ?, unrealized_pnl = ? WHERE id = ?
            """, (current_price, unrealized_pnl, pos["id"]))
            
            # Check liquidation (unrealized_pnl <= -margin)
            if unrealized_pnl <= -pos["margin"]:
                print(f"[Scheduler] LIQUIDATION triggered for position {pos['id']} ({symbol} {pos['direction']})")
                positions_to_close.append((pos["id"], "liquidated"))
            # Check stop loss
            elif pos["stop_loss"]:
                if (pos["direction"] == "LONG" and current_price <= pos["stop_loss"]) or \
                   (pos["direction"] == "SHORT" and current_price >= pos["stop_loss"]):
                    print(f"[Scheduler] STOP LOSS triggered for position {pos['id']} ({symbol})")
                    positions_to_close.append((pos["id"], "stop_loss"))
            # Check take profit
            elif pos["take_profit"]:
                if (pos["direction"] == "LONG" and current_price >= pos["take_profit"]) or \
                   (pos["direction"] == "SHORT" and current_price <= pos["take_profit"]):
                    print(f"[Scheduler] TAKE PROFIT triggered for position {pos['id']} ({symbol})")
                    positions_to_close.append((pos["id"], "take_profit"))
        
        conn.commit()
        conn.close()
        
        # Now close positions AFTER releasing the connection
        if positions_to_close:
            set_current_user(SCHEDULER_USER_ID)
            from trading_tools import close_position
            for pos_id, reason in positions_to_close:
                try:
                    result = close_position(pos_id, reason=reason)
                    print(f"[Scheduler] Position {pos_id} closed: {result}")
                except Exception as e:
                    print(f"[Scheduler] Error closing position {pos_id}: {e}")
                    
    except Exception as e:
        print(f"[Scheduler] Error updating positions: {e}")

def trigger_strategy():
    """Trigger agent strategy analysis"""
    round_id = datetime.now().strftime("%Y-%m-%d_%H:%M")
    symbols = "BTC,ETH,SOL"
    
    print(f"\n[Scheduler] ========== Strategy Round: {round_id} ==========")
    print(f"[Scheduler] Analyzing symbols: {symbols}")
    
    try:
        # Call the Agent API with form-urlencoded (matching frontend format)
        # Prompt includes full strategy execution: open/close positions, adjust SL/TP
        strategy_prompt = f"""构建合约交易策略，分析币种({symbols})：

1. 分析市场多维共振信号（技术面、宏观面、消息面）
2. 检查当前持仓状态和盈亏情况
3. 根据分析结果执行策略：
   - 如有明确开仓信号，使用 open_position 开仓
   - 如需调整现有仓位的止损止盈，使用 update_stop_loss_take_profit 执行调整
   - 如需平仓，使用 close_position 平仓
4. 记录策略分析结果

重要：如果分析结论中包含止损止盈调整建议，必须调用 update_stop_loss_take_profit 工具执行调整，不要只记录不执行。"""
        
        response = requests.post(
            f"{AGENT_API_URL}/agents/trading-strategy-agent/runs",
            data={
                "message": strategy_prompt,
                "user_id": SCHEDULER_USER_ID,
                "session_id": f"strategy-{SCHEDULER_USER_ID[:8]}_{round_id.replace(':', '-')}",
                "stream": "False"
            },
            timeout=120  # 2 minutes timeout for full analysis
        )
        
        if response.status_code == 200:
            print(f"[Scheduler] Strategy completed successfully")
            # Agent已经通过log_strategy_analysis记录日志，这里不再重复记录
        else:
            print(f"[Scheduler] Error: {response.status_code} - {response.text}")
            log_strategy_round(round_id, symbols, {"content": f"Error: {response.status_code}"})
            
    except Exception as e:
        print(f"[Scheduler] Exception during strategy: {e}")
        log_strategy_round(round_id, symbols, {"content": f"Exception: {str(e)}"})
    
    print(f"[Scheduler] ========== Round Complete ==========\n")


# ============= Price Alert Monitoring =============

def check_price_alerts():
    """Check if any price alerts have been triggered and call agent"""
    from price_alerts import get_pending_alerts, mark_alert_triggered
    from trading_tools import get_current_price
    
    pending_alerts = get_pending_alerts()
    
    if not pending_alerts:
        return
    
    # Get current prices for all symbols with alerts
    symbols = list(set(alert["symbol"] for alert in pending_alerts))
    current_prices = {symbol: get_current_price(symbol) for symbol in symbols}
    
    triggered_alerts = []
    
    for alert in pending_alerts:
        symbol = alert["symbol"]
        current_price = current_prices.get(symbol, 0)
        
        if current_price <= 0:
            continue
        
        trigger_price = alert["trigger_price"]
        condition = alert["trigger_condition"]
        
        triggered = False
        
        if condition == "above" and current_price >= trigger_price:
            triggered = True
        elif condition == "below" and current_price <= trigger_price:
            triggered = True
        
        if triggered:
            mark_alert_triggered(alert["id"])
            alert["current_price"] = current_price
            triggered_alerts.append(alert)
            print(f"[Scheduler] 🔔 Price alert triggered: {symbol} {condition} ${trigger_price:,.0f} (current: ${current_price:,.0f})")
    
    # Call agent for each triggered alert
    for alert in triggered_alerts:
        trigger_agent_on_alert(alert)


def trigger_agent_on_alert(alert: dict):
    """Trigger agent to analyze when a price alert is triggered"""
    symbol = alert["symbol"]
    trigger_price = alert["trigger_price"]
    condition = alert["trigger_condition"]
    strategy_context = alert.get("strategy_context", "")
    current_price = alert.get("current_price", 0)
    
    condition_text = "突破" if condition == "above" else "跌破"
    
    print(f"[Scheduler] Calling agent for triggered alert: {symbol}")
    
    try:
        # Construct alert context prompt
        alert_prompt = f"""⚠️ 价格警报触发！

**警报信息**:
- 币种: {symbol}
- 触发条件: {condition_text} ${trigger_price:,.0f}
- 当前价格: ${current_price:,.0f}
- 原策略上下文: {strategy_context}

**你需要做的**:
1. 验证价格走势是否符合原策略预期
2. 重新分析当前市场状况
3. 决定是否执行开仓/平仓操作
4. 如不符合预期，可以放弃或设置新的警报

请执行完整分析后做出决策。"""
        
        response = requests.post(
            f"{AGENT_API_URL}/agents/trading-strategy-agent/runs",
            data={
                "message": alert_prompt,
                "user_id": SCHEDULER_USER_ID,
                "session_id": f"alert-{alert['id']}-{datetime.now().strftime('%H%M')}",
                "stream": "False"
            },
            timeout=120
        )
        
        if response.status_code == 200:
            print(f"[Scheduler] Alert analysis completed for {symbol}")
        else:
            print(f"[Scheduler] Alert analysis error: {response.status_code}")
            
    except Exception as e:
        print(f"[Scheduler] Exception during alert analysis: {e}")


# ============= Daily Report Generation =============

def save_report_to_db(report_date: str, content: str, language: str):
    """Save daily report directly to database"""
    from datetime import datetime
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Ensure table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date TEXT NOT NULL,
            language TEXT DEFAULT 'en',
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(report_date, language)
        )
    """)
    
    # Insert or replace report
    cursor.execute("""
        INSERT OR REPLACE INTO daily_reports (report_date, language, content, created_at)
        VALUES (?, ?, ?, ?)
    """, (report_date, language, content, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()

def generate_daily_report():
    """Generate daily crypto report by calling the agent"""
    from datetime import date
    import traceback
    
    report_date = str(date.today())
    
    print(f"\n[DailyReport] ========== Starting Report Generation ==========")
    print(f"[DailyReport] Date: {report_date}")
    print(f"[DailyReport] Agent API URL: {AGENT_API_URL}")
    print(f"[DailyReport] DB Path: {DB_PATH}")
    
    # Generate reports in both languages
    for language in ["en", "zh"]:
        try:
            print(f"\n[DailyReport] Generating {language} report...")
            
            if language == "en":
                prompt = "Generate today's Crypto Daily Brief following the standard 'Alpha Intelligence' format."
            else:
                prompt = "请按照【Alpha情报局】的标准格式生成今日加密早报。"
            
            # Call agent API - routes to DailyReportAgent
            # Uses multipart/form-data format
            agent_id = "daily-report-agent"
            api_url = f"{AGENT_API_URL}/agents/{agent_id}/runs"
            print(f"[DailyReport] Calling {api_url} ...")
            response = requests.post(
                api_url,
                data={
                    "message": prompt,
                    "user_id": SCHEDULER_USER_ID,
                    "stream": "false"
                },
                timeout=180  # Increased timeout to 3 minutes
            )
            
            print(f"[DailyReport] Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("content", "")
                
                if content:
                    print(f"[DailyReport] Got content, length: {len(content)} chars")
                    # Save directly to database (avoid FastAPI import issues)
                    save_report_to_db(report_date, content, language)
                    print(f"[DailyReport] ✓ {language} report saved successfully")
                else:
                    print(f"[DailyReport] ✗ Agent returned empty content")
                    print(f"[DailyReport] Full response: {data}")
            else:
                print(f"[DailyReport] ✗ Agent API error: {response.status_code}")
                print(f"[DailyReport] Response text: {response.text[:500]}")
                
        except requests.exceptions.Timeout:
            print(f"[DailyReport] ✗ Request timeout for {language} report")
        except requests.exceptions.ConnectionError as e:
            print(f"[DailyReport] ✗ Connection error for {language}: {e}")
        except Exception as e:
            print(f"[DailyReport] ✗ Error generating {language} report: {e}")
            traceback.print_exc()
    
    print(f"[DailyReport] ========== Report Generation Complete ==========")


def send_daily_report_emails():
    """Send daily report emails to all subscribers"""
    from datetime import date
    report_date = str(date.today())
    
    print(f"\n[DailyReport] Sending emails for {report_date}...")
    
    try:
        from app.routers.daily_report import get_all_subscribers, get_db
        from services.email_service import send_daily_report_email
        
        subscribers = get_all_subscribers()
        
        if not subscribers:
            print("[DailyReport] No subscribers to send to")
            return
        
        # Get reports for both languages
        conn = get_db()
        
        for sub in subscribers:
            lang = sub.get("language", "en")
            
            # Get report content for this language
            row = conn.execute("""
                SELECT content FROM daily_reports 
                WHERE report_date = ? AND language = ?
            """, (report_date, lang)).fetchone()
            
            if row:
                success = send_daily_report_email(
                    to_email=sub["email"],
                    report_date=report_date,
                    content=row["content"],
                    unsubscribe_token=sub["token"]
                )
                if success:
                    print(f"[DailyReport] Email sent to {sub['email']}")
        
        conn.close()
        print(f"[DailyReport] Email sending completed")
        
    except Exception as e:
        print(f"[DailyReport] Error sending emails: {e}")


def main():
    """Standalone scheduler entry point (for running as independent process)"""
    global _scheduler_running
    _scheduler_running = True
    
    try:
        _run_scheduler_loop()
    except KeyboardInterrupt:
        print("\n[Scheduler] Stopped by user (Ctrl+C)")
        _scheduler_running = False

if __name__ == "__main__":
    main()

