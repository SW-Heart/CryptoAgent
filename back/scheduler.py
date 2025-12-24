"""
Strategy Scheduler - Automated 4-hour strategy trigger

Run as independent process: python scheduler.py
"""
import schedule
import time
import sqlite3
import json
from datetime import datetime
import requests

# Configuration
AGENT_API_URL = "http://localhost:8000"  # FastAPI server
DB_PATH = "tmp/test.db"

# Use admin user ID for all scheduler operations
from trading_tools import STRATEGY_ADMIN_USER_ID, set_current_user
SCHEDULER_USER_ID = STRATEGY_ADMIN_USER_ID  # Scheduler runs as admin

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
        positions = conn.execute("SELECT * FROM positions WHERE status = 'OPEN'").fetchall()
        
        for pos in positions:
            symbol = pos["symbol"]
            
            # Get current price
            try:
                resp = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT", timeout=5)
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
            f"{AGENT_API_URL}/agents/crypto-analyst-agent/runs",
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

# ============= Daily Report Generation =============

def generate_daily_report():
    """Generate daily crypto report by calling the agent"""
    from datetime import date
    report_date = str(date.today())
    
    print(f"\n[DailyReport] Generating report for {report_date}...")
    
    # Generate reports in both languages
    for language in ["en", "zh"]:
        try:
            if language == "en":
                prompt = """Generate a comprehensive Crypto Daily Report for today. Include:
1. **Market Overview**: BTC, ETH prices and 24h changes, Fear & Greed Index
2. **Top News**: Summarize the most important crypto news today
3. **Market Analysis**: Key trends and patterns observed
4. **Investment Insights**: Potential opportunities and risks to watch
5. **Notable Events**: Any significant events (ETF flows, whale movements, etc.)

Format the output in clean Markdown with clear sections."""
            else:
                prompt = """生成今日加密货币日报。包括：
1. **市场概况**：BTC、ETH 价格和24小时涨跌幅，恐惧贪婪指数
2. **今日要闻**：总结今日最重要的加密货币新闻
3. **市场分析**：观察到的关键趋势和模式
4. **投资建议**：值得关注的潜在机会和风险
5. **重要事件**：任何重要事件（ETF资金流向、巨鲸动向等）

请使用清晰的 Markdown 格式，分段输出。"""
            
            # Call agent API
            response = requests.post(
                f"{AGENT_API_URL}/v1/runs",
                json={
                    "user_id": SCHEDULER_USER_ID,
                    "input": prompt
                },
                timeout=120
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("content", "")
                
                if content:
                    # Save to database
                    from app.routers.daily_report import save_daily_report
                    save_daily_report(report_date, content, language)
                    print(f"[DailyReport] Generated {language} report successfully")
            else:
                print(f"[DailyReport] Agent API error: {response.status_code}")
                
        except Exception as e:
            print(f"[DailyReport] Error generating {language} report: {e}")
    
    print(f"[DailyReport] Report generation completed for {report_date}")


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
    print("[Scheduler] Starting Strategy Nexus Scheduler...")
    print("[Scheduler] Strategy triggers HOURLY at :30 (every hour)")
    print("[Scheduler] Position monitor runs every 10 seconds")
    print("[Scheduler] Daily Report: UTC 0:00 generation, UTC 0:05 emails")
    print()
    
    # Schedule strategy at fixed times (every 1 hour, at :30)
    for hour in range(24):
        time_str = f"{hour:02d}:30"
        schedule.every().day.at(time_str).do(trigger_strategy)
    
    # Schedule position price updates every 10 seconds
    schedule.every(10).seconds.do(update_positions_prices)
    
    # Schedule daily report generation at UTC 0:00
    schedule.every().day.at("00:00").do(generate_daily_report)
    
    # Schedule daily report emails at UTC 0:05
    schedule.every().day.at("00:05").do(send_daily_report_emails)
    
    # Run position update immediately
    update_positions_prices()
    
    # Note: Strategy only runs at scheduled times (00:30, 04:30, 08:30, 12:30, 16:30, 20:30 UTC)
    # trigger_strategy()  # Disabled: no immediate execution on startup
    
    print("[Scheduler] Scheduler is running. Press Ctrl+C to stop.")
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
