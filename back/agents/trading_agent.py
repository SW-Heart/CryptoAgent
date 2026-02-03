"""
Trading Strategy Agent - Lightweight agent for automated strategy execution

This agent is designed specifically for scheduler-triggered strategy analysis.
It has a streamlined System Prompt to reduce token consumption while maintaining
full analytical capabilities.
"""
import os
from dotenv import load_dotenv
from os import getenv
from agno.agent import Agent
# from agno.db.sqlite import SqliteDb
from custom_db import WalSqliteDb as SqliteDb
from agno.models.deepseek import DeepSeek
#from agno.os import AgentOS


# Load environment variables
load_dotenv()

LLM_KEY = getenv("OPENAI_API_KEY")

# 导入合并工具 (减少 token 消耗)
from tools.crypto_tools import (
    get_macro_overview,           # 合并: 恐贪 + BTC主导率 + 市值
    get_key_levels,               # 关键位一站式
    get_pro_crypto_news,          # 新闻 (独立，内容长)
    get_trending_tokens,          # 热门代币榜
)

# 导入聚合技术指标工具
from tools.technical_aggregator import get_all_technical_indicators

# 导入 K 线图视觉分析工具
from kline_analysis import analyze_kline

# 导入ETF工具 (宏观参考)
from tools.etf_tools import get_etf_daily
# 导入Polymarket工具 (市场预测/宏观)
from tools.polymarket import get_market_odds

# 导入交易执行工具
# 注意：使用 Binance 版本进行真实交易，同时保留虚拟版本的一些工具
from tools.binance_trading_tools import (
    binance_open_position as open_position,
    binance_close_position as close_position,
    binance_get_positions_summary as get_positions_summary,
    binance_get_current_price as get_current_price,
    binance_update_stop_loss as update_stop_loss,
    # Phase 2-4 新增工具
    binance_place_trailing_stop as place_trailing_stop,  # 跟踪止损
    binance_get_funding_rate as get_funding_rate,        # 资金费率
    binance_get_adl_risk as get_adl_risk,                # ADL风险
    calculate_position_size,                             # 动态仓位 (Phase 5)
)

# 虚拟交易版本的日志和警报工具（这些不涉及 Binance）
from tools.trading_tools import (
    log_strategy_analysis,
    # 价格警报工具
    set_price_alert,
    get_price_alerts,
    cancel_price_alert,
)


# ==========================================
# Trading Strategy Agent
# ==========================================

# ========== Token Usage Monitor ==========
def monitor_tool_usage(func):
    """Wrapper to log tool input/output sizes for token debugging"""
    def wrapper(*args, **kwargs):
        tool_name = func.__name__
        # Log input size (approx)
        input_str = str(args) + str(kwargs)
        print(f"\n[TokenMonitor] 🟢 CALLING {tool_name}...")
        print(f"[TokenMonitor]    Input Size: {len(input_str)} chars")
        
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Log output size
            result_str = str(result)
            result_len = len(result_str)
            print(f"[TokenMonitor] 🟡 FINISHED {tool_name} ({duration:.2f}s)")
            print(f"[TokenMonitor]    Output Size: {result_len} chars")
            
            # Alert on massive outputs (>20k chars approx 5k tokens)
            if result_len > 10000:
                print(f"[TokenMonitor] ⚠️ HUGE OUTPUT DETECTED (>10k chars) for {tool_name}!")
                print(f"[TokenMonitor]    Preview: {result_str[:200]}...")
            
            return result
        except Exception as e:
            print(f"[TokenMonitor] 🔴 ERROR in {tool_name}: {e}")
            raise e
    return wrapper

import time
import functools
import asyncio

# ========== Token Usage Monitor ==========
def monitor_tool_usage(func):
    """Wrapper to log tool input/output sizes for token debugging"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        tool_name = func.__name__
        input_str = str(args) + str(kwargs)
        print(f"\n[TokenMonitor] 🟢 CALLING {tool_name}...")
        print(f"[TokenMonitor]    Input Size: {len(input_str)} chars")
        
        start_time = time.time()
        try:
            # Check if function is a coroutine
            if asyncio.iscoroutinefunction(func):
                # This might be tricky inside a sync wrapper if the runner is sync
                # But Agno tools are often called in a way that respects their nature
                # Let's handle sync first, but wraps is the key for Metadata
                result = func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
                
            duration = time.time() - start_time
            result_str = str(result)
            result_len = len(result_str)
            print(f"[TokenMonitor] 🟡 FINISHED {tool_name} ({duration:.2f}s)")
            print(f"[TokenMonitor]    Output Size: {result_len} chars")
            
            if result_len > 10000:
                print(f"[TokenMonitor] ⚠️ HUGE OUTPUT DETECTED (>10k chars) for {tool_name}!")
                print(f"[TokenMonitor]    Preview: {result_str[:200]}...")
            
            return result
        except Exception as e:
            print(f"[TokenMonitor] 🔴 ERROR in {tool_name}: {e}")
            raise e
    return wrapper

trading_agent = Agent(
    name="TradingStrategy",
    id="trading-strategy-agent",
    model=DeepSeek(id="deepseek-chat", api_key=LLM_KEY),
    tools=[monitor_tool_usage(t) for t in [
        # ========== 一站式查询工具 ==========
        get_macro_overview,           # 宏观一站式
        # ========== 聚合技术分析 (核心) ==========
        get_all_technical_indicators, # 包含: 趋势、MACD、Vegas、成交量、形态、共振区、历史可靠性
        # ========== K 线视觉分析 (核心) ==========
        analyze_kline,                 # K 线图视觉形态分析 (CHART-IMG + GPT-4o-mini)
        
        # ========== 持仓与警报 ==========
        get_positions_summary,        # Binance 持仓汇总
        get_price_alerts,             # 价格警报列表
        get_adl_risk,                 # ADL 风险等级 (Phase 3)

        # ========== 交易执行 ==========
        open_position,                # Binance 开仓
        close_position,               # Binance 平仓
        update_stop_loss,             # Binance 更新止损
        place_trailing_stop,          # Binance 跟踪止损 (Phase 4)
        get_funding_rate,             # Binance 资金费率 (Phase 2)
        calculate_position_size,      # 动态仓位计算 (Phase 5)
        
        set_price_alert,              # 设置警报
        cancel_price_alert,           # 取消警报
        log_strategy_analysis,        # 记录策略分析
    ]],
    instructions=["""
# 交易策略执行 Agent (Trading Strategy Expert)

你是专注于合约交易的高级交易员。你的核心能力是在海量数据中发现高胜率机会并精准执行。

---

## ⚡ 直接执行模式


**当用户明确提供完整交易参数时，无需纠结，立即执行！**

识别条件:
- 包含: 标的 + 方向(多/空) + [入场/止损/止盈/杠杆] 相关参数。
- 关键词: "立即开仓"、"直接执行"、"按此下单"。

执行流程:
1. 调用 binance_get_positions_summary() 检查余额。
2. 直接调用 binance_open_position() 执行指令。

---

## 🕵️ 职业交易员工作流


对于需要分析的请求，严格遵守以下流程，确保"数据共振"：

### 第一步: 数据共振分析 (One-Shot)
 
- 调用 `get_all_technical_indicators(symbols, timeframe="1d")` 获取全面报告。
- 重点关注报告中的 "TREND STRUCTURE" (日线与 4H 是否共振) 和 "CONFLUENCE ZONES" (共振支撑位)。
- 检查 "HISTORICAL RELIABILITY"：如果某个指标在过去 30 笔交易中表现极差，请降低其权重。
- 顺大逆小原则：日线多头 + 4H 回踩支撑 + 缩量 (Volume Analysis) → **BUY**。

### 第二步: 视觉形态确认 (按需)

- **仅当**技术指标分析出现强烈冲突，或者价格处于关键突破边缘时，调用 `analyze_kline(symbol, intervals="4h")`。
- 不要为每个币种都调用视觉分析，只分析最有潜力的那一个。
- 视觉 LLM 会识别你可能在数值计算中忽略的：**形态 (旗形/楔形)、和谐形态、甚至潜在的陷阱**。
 
### 第三步: 智能仓位与风控

- **动态仓位计算 (CORE)**:
    - 调用 `calculate_position_size(symbol, stop_loss, risk_percent=1.0)`。
    - **CRITICAL**: 开仓时必须使用工具返回的 `quantity`，严禁凭感觉设置下单数量。
- **资金费率检查**: 在开仓前，务必调用 `get_funding_rate(symbol)`。
    - 如果做多且资金费率 > 0.05% (极度拥挤拥)，请警告用户或放弃交易。
    - 如果做空且资金费率 < -0.05%，请警告用户。
- **风险评估**: 
    - 止损设定：支撑位下方 1% 或结构位 - ATR。
    - 盈亏比 (R:R)：必须 ≥ 1.5 才可执行。

---

## 🛠️ 工具库使用手册

### 核心分析工具表
| 场景 | 工具 | 目的 |
|-----|-----|-----|
| **全面分析** | `get_all_technical_indicators` | 获取趋势、支撑阻力、量价、形态、可靠性一站式报告 |
| **视觉形态** | `analyze_kline` | 仅在关键时刻辅助确认形态、趋势、视觉陷阱 |
| **锁定利润** | `place_trailing_stop` | 当达到目标位时，使用"跟踪止损"代替市价平仓 |

---

## 🚨 核心原则 (铁律)

1. **保本第一**: 只要触及 TP1 (第一止盈位)，**必须**调用 `update_stop_loss` 将止损移至开仓价。
2. **利润奔跑**: 对于已有浮盈的仓位，**优先建议**使用 `place_trailing_stop(callback_rate=1.0)` 设置移动止损，而不是直接平仓。
3. **严禁扛单**: 止损一旦设定，除非由于重大黑天鹅手动干预平仓，否则严禁向亏损方向移动。
4. **仓位管理**: 严禁固定手数。必须调用 `calculate_position_size`，单笔交易风险(Risk Amount)控制在账户权益的 1%-2% 以内。
5. **优先限价单**: 除非为了止损或紧急追涨，否则优先使用 `open_position(..., order_type="LIMIT")` 限价单开仓。

---

## 📈 输出规范

1. **分析汇报**: 简要陈述 技术面(Technicals) 的共振点，如有视觉分析则补充。
2. **执行建议**: 给出具体的【买入/卖出/观望/设置警报】建议。
3. **参数配置**: 如果建议交易，必须列出：`入场位`、`止损位`、`分批止盈位`。
"""],
    db=SqliteDb(session_table="test_agent", db_file="tmp/trading_agent.db"), # 必须启用db否则报错，但用add_history_to_context=False禁用历史
    add_history_to_context=False, # 每次运行都是独立会话，关闭历史以节省Token
    num_history_runs=0,
    markdown=True,
    add_datetime_to_context=True,
    timezone_identifier="Etc/UTC",
    debug_mode=True, # 开启调试日志
)

# agent_os = AgentOS(
#     agents=[trading_agent],
# )

# app = agent_os.get_app()

# if __name__ == "__main__":
#     agent_os.serve(app="trading_agent:app", reload=True)