"""
Agent Execution Memory - 跨心跳分析记忆持久化

解决 Agent "金鱼记忆"问题：每次心跳/警报唤醒都是全新的 Agent.run()，
上一次分析的结论（趋势判断、关键价位、计划）全部丢失。

通过在 PostgreSQL 中持久化每个 trader_instance 的分析摘要，
让 Agent 每次被唤醒时都能看到"上一次自己做了什么判断"。

Usage:
    # 读取（在 build_strategy_context 中调用）
    memory = load_execution_memory(user_id, trader_instance_id)

    # 写入（在 log_strategy_analysis 中调用）
    save_execution_memory(user_id, trader_instance_id, summary, plan, observations)
"""
import json
from typing import Optional, Dict, List
from app.database import get_db_connection as get_db


def load_execution_memory(user_id: str, trader_instance_id: int) -> Optional[Dict]:
    """读取指定 trader 实例的上一次分析记忆。

    Returns:
        dict with keys: last_analysis_summary, active_trade_plan, observations, updated_at
        如果没有历史记录则返回 None
    """
    if not user_id or not trader_instance_id:
        return None

    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT last_analysis_summary, active_trade_plan, observations, updated_at
                FROM agent_execution_memory
                WHERE user_id = %s AND trader_instance_id = %s
            """, (user_id, trader_instance_id))
            row = cursor.fetchone()
            if not row:
                return None

            return {
                "last_analysis_summary": row["last_analysis_summary"] or {},
                "active_trade_plan": row["active_trade_plan"] or "",
                "observations": row["observations"] or [],
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else "",
            }
    except Exception as e:
        print(f"[ExecutionMemory] Error loading memory: {e}")
        return None
    finally:
        conn.close()


def save_execution_memory(
    user_id: str,
    trader_instance_id: int,
    last_analysis_summary: Dict,
    active_trade_plan: str = "",
    observations: List[str] = None,
) -> bool:
    """写入/更新指定 trader 实例的分析记忆。

    使用 UPSERT 确保每个 (user_id, trader_instance_id) 只保留最新一条。
    observations 采用追加模式，最多保留最近 10 条。

    Args:
        user_id: 用户 ID
        trader_instance_id: 交易员实例 ID
        last_analysis_summary: 本次分析的结构化摘要
        active_trade_plan: 当前活跃的交易计划描述
        observations: 本次新增的观察列表
    """
    if not user_id or not trader_instance_id:
        return False

    conn = get_db()
    try:
        with conn.cursor() as cursor:
            # 先读取已有的 observations 用于追加
            existing_obs = []
            cursor.execute("""
                SELECT observations FROM agent_execution_memory
                WHERE user_id = %s AND trader_instance_id = %s
            """, (user_id, trader_instance_id))
            row = cursor.fetchone()
            if row and row["observations"]:
                existing_obs = row["observations"] if isinstance(row["observations"], list) else []

            # 追加新观察，保留最近 10 条
            if observations:
                existing_obs.extend(observations)
            merged_obs = existing_obs[-10:]

            # UPSERT
            cursor.execute("""
                INSERT INTO agent_execution_memory
                    (user_id, trader_instance_id, last_analysis_summary, active_trade_plan, observations, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (user_id, trader_instance_id) DO UPDATE SET
                    last_analysis_summary = EXCLUDED.last_analysis_summary,
                    active_trade_plan = EXCLUDED.active_trade_plan,
                    observations = EXCLUDED.observations,
                    updated_at = NOW()
            """, (
                user_id,
                trader_instance_id,
                json.dumps(last_analysis_summary, ensure_ascii=False),
                active_trade_plan or "",
                json.dumps(merged_obs, ensure_ascii=False),
            ))
            conn.commit()
            return True
    except Exception as e:
        print(f"[ExecutionMemory] Error saving memory: {e}")
        return False
    finally:
        conn.close()
