"""
价格警报系统 (Price Alert System)

提供价格警报的存储、查询、触发功能。
当价格达到预设条件时，自动触发Agent进行分析决策。
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional


# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), "tmp", "price_alerts.db")


def get_db():
    """获取数据库连接"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_alerts_table():
    """初始化警报表"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS price_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            trigger_price REAL NOT NULL,
            trigger_condition TEXT NOT NULL,
            strategy_context TEXT,
            created_at TEXT NOT NULL,
            triggered_at TEXT,
            status TEXT DEFAULT 'pending',
            created_by TEXT DEFAULT 'trading-agent'
        )
    """)
    
    # 创建索引
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_alerts_status 
        ON price_alerts(status)
    """)
    
    conn.commit()
    conn.close()


def create_alert(
    symbol: str,
    trigger_price: float,
    trigger_condition: str,
    strategy_context: str = None,
    created_by: str = "trading-agent"
) -> int:
    """
    创建价格警报
    
    Args:
        symbol: 交易对符号 (BTC, ETH, SOL)
        trigger_price: 触发价格
        trigger_condition: 触发条件 ("above" 或 "below")
        strategy_context: 策略上下文（Agent设置警报时的分析）
        created_by: 创建者
    
    Returns:
        新创建的警报ID
    """
    init_alerts_table()
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO price_alerts 
        (symbol, trigger_price, trigger_condition, strategy_context, created_at, status, created_by)
        VALUES (?, ?, ?, ?, ?, 'pending', ?)
    """, (
        symbol.upper(),
        trigger_price,
        trigger_condition.lower(),
        strategy_context,
        datetime.now().isoformat(),
        created_by
    ))
    
    alert_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return alert_id


def get_pending_alerts() -> List[Dict]:
    """获取所有待触发的警报"""
    init_alerts_table()
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM price_alerts 
        WHERE status = 'pending'
        ORDER BY created_at DESC
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def get_alerts_by_symbol(symbol: str) -> List[Dict]:
    """获取指定币种的所有待触发警报"""
    init_alerts_table()
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM price_alerts 
        WHERE symbol = ? AND status = 'pending'
        ORDER BY created_at DESC
    """, (symbol.upper(),))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def mark_alert_triggered(alert_id: int) -> bool:
    """标记警报为已触发"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE price_alerts 
        SET status = 'triggered', triggered_at = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), alert_id))
    
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    
    return affected > 0


def cancel_alert(alert_id: int) -> bool:
    """取消警报"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE price_alerts 
        SET status = 'cancelled'
        WHERE id = ? AND status = 'pending'
    """, (alert_id,))
    
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    
    return affected > 0


def cancel_alerts_by_symbol(symbol: str) -> int:
    """取消指定币种的所有待触发警报"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE price_alerts 
        SET status = 'cancelled'
        WHERE symbol = ? AND status = 'pending'
    """, (symbol.upper(),))
    
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    
    return affected


def check_price_triggers(current_prices: Dict[str, float]) -> List[Dict]:
    """
    检查当前价格是否触发任何警报
    
    Args:
        current_prices: 当前价格字典 {"BTC": 95000, "ETH": 3400, ...}
    
    Returns:
        被触发的警报列表
    """
    pending_alerts = get_pending_alerts()
    triggered_alerts = []
    
    for alert in pending_alerts:
        symbol = alert["symbol"]
        current_price = current_prices.get(symbol)
        
        if current_price is None:
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
    
    return triggered_alerts


def get_alert_summary() -> str:
    """获取警报摘要（供Agent查看）"""
    pending = get_pending_alerts()
    
    if not pending:
        return "当前没有待触发的价格警报。"
    
    summary = f"📢 当前有 {len(pending)} 个待触发警报：\n\n"
    
    for alert in pending:
        condition_text = "突破" if alert["trigger_condition"] == "above" else "跌破"
        summary += f"- {alert['symbol']}: {condition_text} ${alert['trigger_price']:,.0f}\n"
        if alert["strategy_context"]:
            # 只显示策略的前100字符
            ctx = alert["strategy_context"][:100]
            summary += f"  策略: {ctx}...\n"
    
    return summary


# 初始化表
init_alerts_table()
