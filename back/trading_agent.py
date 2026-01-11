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
from agno.db.sqlite import SqliteDb
from agno.models.deepseek import DeepSeek
#from agno.os import AgentOS


# Load environment variables
load_dotenv()

LLM_KEY = getenv("OPENAI_API_KEY")

# 导入合并工具 (减少 token 消耗)
from crypto_tools import (
    get_macro_overview,           # 合并: 恐贪 + BTC主导率 + 市值
    get_batch_technical_analysis, # 合并: 周期对齐 + EMA + ATR + 费率
    get_key_levels,               # 合并: Fib + EMA + POC + 共振区
    get_pro_crypto_news,          # 新闻 (独立，内容长)
    get_trending_tokens,          # 热门代币榜
)

# 导入专业技术分析工具
from technical_analysis import (
    get_multi_timeframe_analysis,
    get_ema_structure,
    get_vegas_channel,
    get_macd_signal,
    get_volume_analysis,
    get_volume_profile
)

# 导入趋势线分析
from pattern_recognition import (
    get_trendlines,
)

# 导入历史规律记忆
from indicator_memory import get_indicator_reliability, get_indicator_reliability_all_timeframes

# 导入 K 线图视觉分析工具
from kline_analysis import analyze_kline

# 导入ETF工具 (宏观参考)
from etf_tools import get_etf_daily

# 导入交易执行工具
# 注意：使用 Binance 版本进行真实交易，同时保留虚拟版本的一些工具
from binance_trading_tools import (
    binance_open_position as open_position,
    binance_close_position as close_position,
    binance_get_positions_summary as get_positions_summary,
    binance_get_current_price as get_current_price,
    binance_update_stop_loss as update_stop_loss,
)

# 虚拟交易版本的日志和警报工具（这些不涉及 Binance）
from trading_tools import (
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
        get_batch_technical_analysis, # 综合技术分析一站式
        get_key_levels,               # 关键位一站式
        get_pro_crypto_news,          # 深度新闻
        get_trending_tokens,          # 热门代币榜
        get_etf_daily,                # ETF 资金流
        
        # ========== 专业技术分析 (细颗粒度) ==========
        get_multi_timeframe_analysis,  # 多周期综合 (主入口)
        get_ema_structure,             # EMA 均线结构分析
        get_vegas_channel,             # Vegas 通道分析
        get_macd_signal,               # MACD 信号分析
        get_volume_analysis,           # 量价关系分析
        get_volume_profile,            # 密集成交区识别
        get_trendlines,                # 趋势线识别
        get_indicator_reliability,     # 指标历史可靠性
        get_indicator_reliability_all_timeframes,
        
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

## ⚡ 直接执行模式 (Fast Track)

**当用户明确提供完整交易参数时，无需纠结，立即执行！**

识别条件:
- 包含: 标的 + 方向(多/空) + [入场/止损/止盈/杠杆] 相关参数。
- 关键词: "立即开仓"、"直接执行"、"按此下单"。

执行流程:
1. 调用 binance_get_positions_summary() 检查余额。
2. 直接调用 binance_open_position() 执行指令。

---

## 🕵️ 职业交易员工作流 (Analytical Track)

对于需要分析的请求，严格遵守以下流程，确保"数据共振"：

### Step 1: 视觉验证 (The Edge)
- **CRITICAL**: 在做任何决策前，必须先调用 `analyze_kline(symbol, intervals="D,240")`。
- 视觉 LLM 会识别你可能在数值计算中忽略的：**形态 (旗形/楔形)、和谐形态、甚至潜在的陷阱**。
- 将视觉分析结论作为你决策的最重要权重之一。

### Step 2: 趋势共振分析 (The Compass)
- 调用 `get_multi_timeframe_analysis(symbol)` 检查日线与 4H 周期。
- 只有当日线 (趋势方向) 与 4H (入场点位) 形成 Confluence 时才考虑交易。
- 顺大逆小原则：日线多头 → 4H 回踩支撑 → **BUY**。

### Step 3: 指标可靠性与量价 (The Filter)
- 调用 `get_indicator_reliability(symbol)`。如果某个指标在过去 30 笔交易中表现极差，请降低其权重。
- 调用 `get_volume_analysis(symbol)` 检查是否为"缩量反弹"或"缩量回踩"。

### Step 4: 风险评估与执行 (The Execution)
- 计算止损：使用 `get_volatility_analysis(symbol)` 获取 ATR。
- 止损位：结构位 ± (1.5 × ATR)。
- 检查盈亏比 (R:R)：必须 ≥ 1.5 才可执行开仓。

---

## 🛠️ 工具库使用手册

### 核心分析工具表
| 场景 | 工具 | 目的 |
|-----|-----|-----|
| **视觉形态** | `analyze_kline` | 识别形态、趋势、视觉陷阱 |
| **综合趋势** | `get_multi_timeframe_analysis` | 寻找日线与 4H 的共振信号 |
| **通道/支撑** | `get_vegas_channel`, `get_key_levels` | 寻找具体的入场和防守位 |
| **风险/止损** | `get_volatility_analysis` | 基于波动率计算科学止损距离 |
| **可靠性** | `get_indicator_reliability` | 剔除当前无效的指标信号 |

---

## 🚨 核心原则 (铁律)

1. **保本第一**: 只要触及 TP1 (第一止盈位)，**必须**调用 `binance_update_stop_loss` 将止损移至开仓价。
2. **严禁扛单**: 止损一旦设定，除非由于重大黑天鹅手动干预平仓，否则严禁向亏损方向移动。
3. **仓位管理**: BTC/ETH 单笔风险(SL) 占总权益比例控制在 10% 以内；山寨币控制在 2% 以内。
4. **拒绝噪音**: 1H 周期以下的波动视为噪音，分析至少从 4H 开始。

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