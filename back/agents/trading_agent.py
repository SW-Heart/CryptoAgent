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

trading_agent = Agent(
    name="TradingStrategy",
    id="trading-strategy-agent",
    model=DeepSeek(id="deepseek-chat", api_key=LLM_KEY),
    tools=[
        # ========== 一站式查询工具 ==========
        get_macro_overview,           # 宏观一站式
        # ========== 聚合技术分析 (核心) ==========
        get_all_technical_indicators, # 包含: 趋势、MACD、Vegas、成交量、形态、共振区、历史可靠性
        # ========== K 线视觉分析 (核心) ==========
        analyze_kline,                 # K 线图视觉形态分析 (CHART-IMG + GPT-4o-mini)
        
        # ========== 持仓与警报 ==========
        get_positions_summary,        # Binance 持仓汇总
        get_price_alerts,             # 价格警报列表

        # ========== 交易执行 ==========
        open_position,                # Binance 开仓
        close_position,               # Binance 平仓
        update_stop_loss,             # Binance 更新止损
        set_price_alert,              # 设置警报
        cancel_price_alert,           # 取消警报
        log_strategy_analysis,        # 记录策略分析
    ],
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

### 第一步: 视觉验证

- **CRITICAL**: 在做任何决策前，必须先调用 `analyze_kline(symbol, intervals="D,240")`。
- 视觉 LLM 会识别你可能在数值计算中忽略的：**形态 (旗形/楔形)、和谐形态、甚至潜在的陷阱**。
- 将视觉分析结论作为你决策的最重要权重之一。

### 第二步: 数据共振分析 (One-Shot)
 
- 调用 `get_all_technical_indicators(symbols, timeframe="1d")` 获取全面报告。
- 重点关注报告中的 "TREND STRUCTURE" (日线与 4H 是否共振) 和 "CONFLUENCE ZONES" (共振支撑位)。
- 检查 "HISTORICAL RELIABILITY"：如果某个指标在过去 30 笔交易中表现极差，请降低其权重。
- 顺大逆小原则：日线多头 + 4H 回踩支撑 + 缩量 (Volume Analysis) → **BUY**。
 
### 第三步: 风险评估与执行
 
- 从 "CONFLUENCE ZONES" 中寻找最近的强支撑作为止损参考。
- 止损设定：支撑位下方 1% 或结构位 - ATR。
- 检查盈亏比 (R:R)：必须 ≥ 1.5 才可执行开仓。

---

## 🛠️ 工具库使用手册

### 核心分析工具表
| 场景 | 工具 | 目的 |
|-----|-----|-----|
| **视觉形态** | `analyze_kline` | 识别形态、趋势、视觉陷阱 |
| **全面分析** | `get_all_technical_indicators` | 获取趋势、支撑阻力、量价、形态、可靠性一站式报告 |

---

## 🚨 核心原则 (铁律)

1. **保本第一**: 只要触及 TP1 (第一止盈位)，**必须**调用 `binance_update_stop_loss` 将止损移至开仓价。
2. **严禁扛单**: 止损一旦设定，除非由于重大黑天鹅手动干预平仓，否则严禁向亏损方向移动。
3. **仓位管理**: BTC/ETH 单笔风险(SL) 占总权益比例控制在 10% 以内；山寨币控制在 2% 以内。
4. **拒绝噪音**: 1H 周期以下的波动视为噪音，分析至少从 4H 开始。
5. **优先限价单**: 除非为了止损或紧急追涨，否则优先使用 `open_position(..., order_type="LIMIT")` 限价单开仓，以降低手续费（Maker 费率）。

---

## 📈 输出规范

1. **分析汇报**: 简要陈述 视觉形态(K-line Vision) + 技术面(Technicals) 的共振点。
2. **执行建议**: 给出具体的【买入/卖出/观望/设置警报】建议。
3. **参数配置**: 如果建议交易，必须列出：`入场位`、`止损位`、`分批止盈位 (TP1/TP2/TP3)`。
"""],
    db=SqliteDb(session_table="test_agent", db_file="tmp/test.db"),
    add_history_to_context=True,
    num_history_runs=3,
    markdown=True,
    add_datetime_to_context=True,
    timezone_identifier="Etc/UTC",
)

# agent_os = AgentOS(
#     agents=[trading_agent],
# )

# app = agent_os.get_app()

# if __name__ == "__main__":
#     agent_os.serve(app="trading_agent:app", reload=True)