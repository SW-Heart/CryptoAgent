"""
Price Alert Tools - Agent 价格警报工具

提供 Agent 自主设置/取消/查看价格警报的能力。
当市场价格到达 Agent 认为的关键位时，自动触发一次分析。

用户隔离：每个 user_id 的警报互不可见。
交易所隔离：根据用户绑定的交易所选择对应的价格数据源。

Usage (Agent 工具):
    set_price_alert(symbol="BTC", target_price=95000, direction="ABOVE", reason="EMA21阻力位突破")
    cancel_price_alert(alert_id=1)
    list_price_alerts()
"""
from typing import Optional
from datetime import datetime

from app.database import get_db_connection as get_db
from tools.trading_tools import get_current_user, get_current_trader_id

# 每用户最大活跃警报数量
MAX_ALERTS_PER_USER = 10


def _get_user_price_source(user_id: str) -> str:
    """根据用户绑定的交易所推断价格数据源。
    
    查找用户当前活跃的 exchange_account 或 trader_instance 绑定的交易所，
    返回对应的 price_source 标识。
    
    Returns:
        "binance" / "okx" / "bybit" / "bitget" / "gate"
    """
    if not user_id:
        return "binance"
    
    try:
        conn = get_db()
        try:
            with conn.cursor() as cursor:
                # 优先查当前 trader_instance 绑定的交易所
                trader_id = None
                try:
                    trader_id = get_current_trader_id()
                except Exception:
                    pass
                
                if trader_id:
                    cursor.execute("""
                        SELECT ea.provider
                        FROM trader_instances ti
                        JOIN exchange_accounts ea ON ea.id = ti.exchange_account_id
                        WHERE ti.id = %s AND ti.user_id = %s
                    """, (trader_id, user_id))
                    row = cursor.fetchone()
                    if row and row.get("provider"):
                        return row["provider"].lower()
                
                # 回退：查默认交易所账户
                cursor.execute("""
                    SELECT provider FROM exchange_accounts
                    WHERE user_id = %s
                    ORDER BY is_connected DESC, is_default DESC, id ASC
                    LIMIT 1
                """, (user_id,))
                row = cursor.fetchone()
                if row and row.get("provider"):
                    return row["provider"].lower()
        finally:
            conn.close()
    except Exception as e:
        print(f"[AlertTools] Error getting price source: {e}")
    
    return "binance"


def set_price_alert(
    symbol: str,
    target_price: float,
    direction: str,
    reason: str = "",
    user_id: str = None,
) -> dict:
    """设置一个价格警报。当价格到达目标位时，自动触发一次策略分析。
    
    Args:
        symbol: 交易标的 (如 "BTC", "ETH", "SOL")
        target_price: 目标触发价格
        direction: 触发方向 —— "ABOVE" (价格上穿) 或 "BELOW" (价格下穿)
        reason: 设置此警报的原因说明 (如 "日线 EMA21 阻力位突破")
        user_id: 用户 ID（通常由系统自动注入）
    
    Returns:
        dict: 创建确认，包含 alert_id
    """
    # 参数校验
    symbol = symbol.upper().strip().replace("USDT", "")
    direction = direction.upper().strip()
    
    if direction not in ("ABOVE", "BELOW"):
        return {"error": "direction 必须是 'ABOVE' 或 'BELOW'"}
    
    if target_price <= 0:
        return {"error": "target_price 必须大于 0"}
    
    # 获取 user_id
    if not user_id:
        user_id = get_current_user()
    if not user_id:
        return {"error": "无法确定用户身份"}
    
    # 获取 trader_instance_id
    trader_id = None
    try:
        trader_id = get_current_trader_id()
    except Exception:
        pass
    
    # 推断价格数据源
    price_source = _get_user_price_source(user_id)
    
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            # 检查活跃警报数量限制
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM price_alerts WHERE user_id = %s AND status = 'ACTIVE'",
                (user_id,)
            )
            count = cursor.fetchone()["cnt"]
            if count >= MAX_ALERTS_PER_USER:
                conn.close()
                return {"error": f"已达到最大活跃警报数量限制 ({MAX_ALERTS_PER_USER})。请先取消一些不再需要的警报。"}
            
            # 防重复：相同 user + symbol + target_price + direction 不重复创建
            cursor.execute("""
                SELECT id FROM price_alerts
                WHERE user_id = %s AND symbol = %s 
                  AND target_price = %s AND direction = %s 
                  AND status = 'ACTIVE'
            """, (user_id, symbol, target_price, direction))
            existing = cursor.fetchone()
            if existing:
                conn.close()
                return {
                    "success": True,
                    "alert_id": existing["id"],
                    "message": f"该警报已存在 (ID: {existing['id']})，无需重复创建"
                }
            
            # 创建警报
            cursor.execute("""
                INSERT INTO price_alerts (user_id, trader_instance_id, symbol, target_price, direction, price_source, reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (user_id, trader_id, symbol, target_price, direction, price_source, reason or ""))
            
            alert_id = cursor.fetchone()["id"]
            conn.commit()
    finally:
        conn.close()
    
    direction_label = "上穿" if direction == "ABOVE" else "下穿"
    return {
        "success": True,
        "alert_id": alert_id,
        "symbol": symbol,
        "target_price": target_price,
        "direction": direction,
        "price_source": price_source,
        "message": f"✅ 已设置警报：当 {symbol} 价格{direction_label} ${target_price:,.2f} 时触发分析。原因：{reason}"
    }


def cancel_price_alert(
    alert_id: int = None,
    symbol: str = None,
    user_id: str = None,
) -> dict:
    """取消价格警报。可按 ID 取消单个，或按标的取消该标的所有活跃警报。
    
    Args:
        alert_id: 警报 ID（取消单个）
        symbol: 标的符号（取消该标的所有警报）
        user_id: 用户 ID（通常由系统自动注入）
    
    Returns:
        dict: 取消确认
    """
    if not alert_id and not symbol:
        return {"error": "请提供 alert_id 或 symbol"}
    
    if not user_id:
        user_id = get_current_user()
    if not user_id:
        return {"error": "无法确定用户身份"}
    
    if symbol:
        symbol = symbol.upper().strip().replace("USDT", "")
    
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            if alert_id:
                # 按 ID 取消单个
                cursor.execute("""
                    UPDATE price_alerts SET status = 'CANCELLED'
                    WHERE id = %s AND user_id = %s AND status = 'ACTIVE'
                """, (alert_id, user_id))
                affected = cursor.rowcount
                if affected == 0:
                    conn.close()
                    return {"error": f"警报 #{alert_id} 不存在或已非活跃状态"}
                conn.commit()
                return {"success": True, "message": f"✅ 已取消警报 #{alert_id}"}
            else:
                # 按 symbol 取消该标的所有活跃警报
                cursor.execute("""
                    UPDATE price_alerts SET status = 'CANCELLED'
                    WHERE user_id = %s AND symbol = %s AND status = 'ACTIVE'
                """, (user_id, symbol))
                affected = cursor.rowcount
                conn.commit()
                if affected == 0:
                    return {"success": True, "message": f"{symbol} 没有活跃警报"}
                return {"success": True, "message": f"✅ 已取消 {symbol} 的 {affected} 个警报"}
    finally:
        conn.close()


def list_price_alerts(user_id: str = None) -> dict:
    """列出当前用户所有活跃的价格警报。
    
    Args:
        user_id: 用户 ID（通常由系统自动注入）
    
    Returns:
        dict: 包含活跃警报列表
    """
    if not user_id:
        user_id = get_current_user()
    if not user_id:
        return {"error": "无法确定用户身份", "count": 0, "list": []}
    
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, symbol, target_price, direction, price_source, reason, 
                       created_at, trader_instance_id
                FROM price_alerts
                WHERE user_id = %s AND status = 'ACTIVE'
                ORDER BY created_at DESC
            """, (user_id,))
            rows = cursor.fetchall()
    finally:
        conn.close()
    
    alerts = []
    for row in rows:
        direction_label = "上穿" if row["direction"] == "ABOVE" else "下穿"
        alerts.append({
            "id": row["id"],
            "symbol": row["symbol"],
            "target_price": row["target_price"],
            "direction": row["direction"],
            "direction_label": direction_label,
            "price_source": row["price_source"],
            "reason": row["reason"] or "",
            "created_at": row["created_at"].isoformat() if row["created_at"] else "",
            "trader_instance_id": row["trader_instance_id"],
        })
    
    return {
        "count": len(alerts),
        "max_allowed": MAX_ALERTS_PER_USER,
        "list": alerts,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 供调度器调用的内部函数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_active_alerts() -> list:
    """获取所有活跃警报（供调度器批量检查使用）。
    
    Returns:
        list of dict，每个 dict 包含警报信息 + user_id
    """
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, user_id, trader_instance_id, symbol, target_price, 
                       direction, price_source, reason
                FROM price_alerts
                WHERE status = 'ACTIVE'
                  AND (cooldown_until IS NULL OR cooldown_until < NOW())
            """)
            return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def mark_alert_triggered(alert_id: int):
    """将警报标记为已触发（由调度器调用）。"""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE price_alerts 
                SET status = 'TRIGGERED', triggered_at = NOW()
                WHERE id = %s AND status = 'ACTIVE'
            """, (alert_id,))
            conn.commit()
    finally:
        conn.close()
