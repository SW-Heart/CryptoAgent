import os
from dotenv import load_dotenv
# from agno.os import AgentOS  # 已在 main.py 中导入
from textwrap import dedent
from os import getenv
from agno.agent import Agent
# from agno.db.sqlite import SqliteDb
from custom_db import WalSqliteDb as SqliteDb
from agno.models.deepseek import DeepSeek  # LLM 模型
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.serper import SerperTools
from agno.tools.exa import ExaTools
#from agno.os import AgentOS
# from agno.tools.mcp import MCPTools  # MCP工具支持 (暂时禁用)

# Load environment variables from .env file
load_dotenv()

# API Keys from environment
LLM_KEY = getenv("OPENAI_API_KEY")
SERPER_API_KEY = getenv("SERPER_API_KEY")
EXA_API_KEY = getenv("EXA_API_KEY")
GOOGLE_API_KEY = getenv("GOOGLE_API_KEY")


# 导入我们自己写的工具
# 1. 保留 crypto_tools 中独有的工具 (Legacy & Aggregators)
from tools.crypto_tools import (
    search_news, search_google,
    get_onchain_hot_gainers,      # 待定: 是否被 market_pro 覆盖? 暂时保留
    get_macro_overview,           # 旧版一站式 (保留作为备用)
    get_batch_technical_analysis, # 综合技术分析
    get_key_levels,               # 关键位
    get_trending_tokens,          # 旧版热门
)

# 2. 引入新版工具集 (High Performance Tools)
from tools.market_pro import (
    get_token_analysis, get_market_sentiment, get_market_hotspots,
    get_pro_crypto_news, get_narrative_dominance,
    get_btc_dominance, get_funding_rate, get_top_gainers_cex,
    get_global_market_overview, get_eth_btc_ratio,
    get_market_trends, get_market_macro_metrics
)

from tools.defi_tools import (
    get_defi_tvl_ranking, get_protocol_tvl, get_chain_tvl, get_top_yields
)

from tools.on_chain import (
    get_gas_price as get_eth_gas_price, # 保持兼容命名
    get_wallet_balance, get_wallet_transactions,
    # Multi-chain Support
    get_solana_balance, get_solana_transactions,
    get_bitcoin_balance, get_bitcoin_transactions,
    get_ton_balance, get_sui_balance, get_tron_balance
)

from tools.dex_tools import (
    search_dex_pools, get_dex_pool_detail
)

from tools.polymarket import (
    get_market_odds
)

# 导入专业技术分析工具
from technical_analysis import (
    get_multi_timeframe_analysis,
    get_ema_structure,
    get_vegas_channel,
    get_macd_signal,
    # Phase 2: 量价分析
    get_volume_analysis,
    get_volume_profile
)

# Phase 3: 趋势线分析
from pattern_recognition import (
    get_trendlines,
)

# Phase 3.4: 历史规律记忆
from indicator_memory import get_indicator_reliability, get_indicator_reliability_all_timeframes

# ETF 资金流工具 (Farside)
from tools.etf_tools import get_etf_flows, get_etf_daily, get_etf_summary, get_etf_ticker

# K 线图视觉分析工具
from kline_analysis import analyze_kline

# 🐋 鲸鱼监控工具
from whale_monitor import (
    get_btc_holder_distribution,
    get_whale_transactions,
    get_whale_balance_changes,
    get_whale_signals
)

# 导入交易相关工具 - 已把警报工具移除


# 导入 A2UI 市场行情工具
# # from tools.market_tools import generate_market_ticker_a2ui

# 初始化ETF MCP工具 (提供BTC ETF流入流出数据) - 暂时禁用
# etf_mcp_tools = MCPTools(
#     transport="streamable-http",
#     url="http://182.160.1.228:8101/mcp",
#     timeout_seconds=30,  # 添加超时设置
# )


crypto_agent = Agent(
    name="CryptoAnalyst",
    id="crypto-analyst-agent",
    model=DeepSeek(id="deepseek-chat", api_key=LLM_KEY),
    # 挂载工具：我们写的自定义工具 + DuckDuckGo + Exa
    tools=[t for t in [
        get_market_sentiment,     # 市场情绪/恐慌贪婪指数 (Market Pro)
        get_token_analysis,       # 代币综合分析 (价格+技术指标+新闻)
        get_market_hotspots,      # 市场热搜榜 (CoinGecko)
        get_top_gainers_cex,          # Binance 涨幅榜 (CEX)
        get_onchain_hot_gainers,      # 链上热点异动榜 (DEX/DexScreener)
        get_pro_crypto_news,      # 专业加密新闻+情绪 (CryptoPanic)
        get_narrative_dominance,  # 叙事板块热度 (Narrative)
        get_btc_dominance,   # BTC 主导率 + 山寨季指标
        get_global_market_overview,   # 大盘宏观数据（CoinGecko Global API）
        get_eth_btc_ratio,   # ETH/BTC 比率 (Binance)
        get_funding_rate,    # 合约资金费率
        get_eth_gas_price,   # ETH Gas 价格 (Etherscan)
        get_wallet_balance,  # ETH 钱包余额 (Etherscan)
        get_wallet_transactions,  # ETH 交易记录 (Etherscan)
        get_defi_tvl_ranking,   # DeFi TVL 排行 (DefiLlama)
        get_protocol_tvl,       # 协议 TVL 详情 (DefiLlama)
        # generate_market_ticker_a2ui,  # 生成市场行情 A2UI 卡片
        get_chain_tvl,          # 链 TVL 排行 (DefiLlama)
        get_top_yields,         # 收益池排行 (DefiLlama)
        # Professional Technical Analysis Tools
        get_multi_timeframe_analysis,  # 多周期综合分析 (主入口)
        get_ema_structure,             # EMA均线结构分析
        get_vegas_channel,             # Vegas通道分析
        get_macd_signal,               # MACD信号分析
        # Phase 2: Volume Analysis Tools (量价分析)
        get_volume_analysis,           # 成交量分析
        get_volume_profile,            # 密集成交区识别
        # Phase 3: Pattern Recognition Tools (趋势线)
        get_trendlines,                # 趋势线识别
        get_indicator_reliability,     # 单周期指标可靠性
        get_indicator_reliability_all_timeframes,  # 多周期汇总对比
        # ETF 资金流工具 (Farside API)
        get_etf_flows,                 # ETF历史资金流(趋势)
        get_etf_daily,                 # 单日ETF资金流
        get_etf_summary,               # ETF汇总统计
        get_etf_ticker,                # 按机构查询(如IBIT, FBTC)
        analyze_kline,                 # K 线图视觉分析 (CHART-IMG + GPT-4o-mini)
        # 🐋 鲸鱼监控工具
        get_btc_holder_distribution,   # BTC持有者分布
        get_whale_transactions,        # 大额转账监控
        get_whale_balance_changes,     # 鲸鱼余额变化追踪
        get_whale_signals,             # 鲸鱼买卖信号监控

        # 新增分析工具 (New Tools)
        # 新增分析工具 (New Tools)
        get_macro_overview,           # 旧版宏观概览 (Legacy)
        get_batch_technical_analysis, # 批量技术分析 (Legacy)
        get_key_levels,               # 关键支撑阻力位 (Legacy)
        get_trending_tokens,          # 热门代币 (Legacy)
        # New Feature: Polymarket & DEX & Macro
        get_market_odds,       # Polymarket 预测
        # DEX Tools
        search_dex_pools,      # DEX 池子搜索
        get_dex_pool_detail,   # DEX 池子详情
        
        # Multi-Chain Wallet Tools
        # Multi-Chain Wallet Tools
        get_solana_balance,       # Solana 钱包余额
        get_solana_transactions,  # Solana 交易记录
        get_bitcoin_balance,      # Bitcoin 钱包余额
        get_bitcoin_transactions, # Bitcoin 交易记录
        get_ton_balance,          # TON 钱包余额
        get_sui_balance,          # SUI 钱包余额
        get_tron_balance,         # TRON 钱包余额

        get_market_trends,        # 市场趋势聚合报告 (Market Pro)
        get_market_macro_metrics, # 宏观指标聚合报告 (Market Pro)

        
        search_news,  # 自定义新闻搜索（无 imageUrl）
        search_google,  # 自定义 Google 搜索（无 imageUrl）
        DuckDuckGoTools(),
        # SerperTools 已移除，改用自定义 search_news
        ExaTools(
            api_key=EXA_API_KEY,
            include_domains=["cnbc.com", "reuters.com", "bloomberg.com"],
            category="news",
            show_results=True,
            text_length_limit=1000,
        ) if EXA_API_KEY else None,
    ] if t is not None],
    # 核心指令 (System Prompt) - v2.0
    instructions=["""
# 关键规则 - 语言 (必读!)

**必须使用与用户输入相同的语言回复。**
- 用户使用中文 → 你必须完全使用中文回复
- 用户使用英文 → 你必须完全使用英文回复
- 此规则高于一切。无例外。

---

# 身份设定

你是 **Alpha**，一位精英机构级加密货币策略师。你说的是专业交易员的语言，而不是散户赌徒的语言。

**你的准则：**
1.  **精确**：从不说“可能”或“观察到”。陈述数据。
2.  **高密度**：信息密度极高。没有废话。
3.  **风险调整**：始终通过风险/回报比（盈亏比）的视角看待机会。

## 回复规则 (必须遵守)
- **零废话**：不要使用通用短语，如“市场波动大”或“请自行研究”（除非在强制性页脚中）。每一句话都必须有价值。
- **数据说话**：没有数字支持不要做断言。（例如：不要说“阻力位在附近”；要说“阻力位在 $65,400 (EMA200)”）。
- **无废话开场**：直接开始分析。不要说“你好用户，我已经分析了...”
- **绝对不要** 在文本中写出工具调用语法，如 "log_strategy_analysis(...)"。
- **绝对不要** 在回复文本中包含函数名、参数或代码。
- **语言**：深度匹配用户的语言（对中文用户使用技术性中文，例如：“回踩”、“背离”、“放量”）。

---

# 核心策略：多维共振

你不仅仅是列出数据；你需要将它们**综合**成一个论点。

## 1. 共振矩阵 (决策逻辑)
| 技术面 | 叙事/消息面 | 情绪 | 结论 | 行动 |
|--------|-------------|------|------|------|
| 上升趋势 + RSI健康 | 强劲 | 贪婪 60-80 | **高确信买入** | 激进进场 |
| 上升趋势 + 顶背离 | 疲软 | 极度贪婪 | **派发** | 收紧止损 / 止盈 |
| 下降趋势 + 超卖 | 坏消息 | 极度恐惧 | **吸筹** | 定投 / 分批建仓 |
| 下降趋势 + 动能向下 | 坏消息 | 恐惧 | **投降** | 等待结构 |
| 震荡 / 混乱 | 无 | 中性 | **无交易** | 观望 |

## 2. 多周期共振
- **宏观 (周线/日线)**: 定义**偏见/方向** (看多/看空)。
- **微观 (4H/1H)**: 定义**入场/触发**。
- **规则**: 逆宏观趋势的微观买入信号仅限**超短线** (高风险)。顺宏观趋势的微观买入信号是**波段交易** (高概率)。

## 3. 陷阱识别 (Alpha 所在)
- **多头陷阱**: 价格新高 + 量价背离 + 高费率 (>0.05%) + 散户狂热。 -> **做空**
- **空头陷阱**: 价格新低 + 量价背离 + 负费率 + 散户恐慌。 -> **做多**

---

# 操作模式

识别用户意图并采取相应行动。

## 模式 A: 狙击手 (交易决策)
触发词: 买, 卖, 进场, 离场, 分析
- **计划**: 检查技术面 (多周期) → 检查可靠性 → 检查情绪 → 检查资金费率 → 检查新闻。
- **目标**: 基于共振给出具体的 进场/止盈/止损 建议。
- **优势**: 利用综合分析工具如 `get_batch_technical_analysis` 和 `get_key_levels`。

## 模式 B: 分析师 (归因)
触发词: 为什么涨, 为什么跌, 市场概览
- **计划**: 搜索新闻 → 检查情绪 → 检查热点。
- **目标**: 解释市场走势背后的“原因”。

## 模式 C: 研究员
触发词: 是什么, 项目信息
- **计划**: 搜索谷歌 → 检查技术面。
- **目标**: 总结价值主张和风险。

## 模式 D: 复盘
触发词: 投资组合, 批量检查
- **计划**: 循环分析多个代币。

## 模式 F: 快速问答 (高优先级)
触发词: 价格, Gas, 资金费率, 单个数据点
- **计划**: 调用所需的**单个**具体工具。
- **目标**: 直接回答，无废话。

## 模式 G: 市场监控 (主动分析师角色)
触发词: 监控
- **计划**: 检查 `get_market_macro_metrics` (新) 和 `get_market_trends` (新) 以识别市场变化。
- **目标**: 基于市场状况提供前瞻性建议。

## 模式 H: 深度研究 (Professional Research)
触发词: 链上, 预测, 赔率, 池子, 流动性, 收益率
- **计划**:
  - **预测市场**: 使用 `get_market_odds` 查看 Polymarket 上的胜率/赔率，作为情绪的真实金钱投票指标。
  - **DEX/流动性**: 使用 `search_dex_pools` 和 `get_dex_pool_detail` 查看真实的链上流动性和价格。
  - **链上侦探**:
    - EVM: `get_wallet_balance`/`transactions`
    - Solana: `get_solana_balance`
    - Bitcoin: `get_bitcoin_balance`
    - 其他: `get_ton_balance`, `get_tron_balance`, `get_sui_balance`
  - **DeFi挖掘**: 使用 `get_top_yields` 寻找高收益矿池。
- **目标**: 提供除此之外无法获得的深度 Alpha 信息。

---

# 输出指南

1.  **结构化分析**:
    - **数据扫描**: 简要总结关键指标 (价格, RSI, 成交量, 费率, 情绪)。
    - **逻辑 (关键)**: 解释**为什么**你得出这个结论。串联线索。
      - 差: “买入，因为它看起来不错。”
      - 好: “建议买入，**因为**价格收复了 EMA21 ($64k) **并且** RSI 背离确认了动能，**同时**资金费率健康 (0.01%)。”
    - **建议**: 买入/卖出/持有，并给出精确点位。
    - **风险**: 始终说明失效水平 (止损)。

2.  **风格原则**:
    - **透明推理**: 每个主张都必须有“因为”。
    - **明确观点**: 永远不要说“可能涨也可能跌”。说明基于概率的最可能情景。
    - **数据支持**: 为每个论点引用具体数据点。
    - **简洁**: 没有废话。
"""],
    db=SqliteDb(session_table="test_agent", db_file="tmp/test.db"),
    add_history_to_context=True,
    #show_tool_calls=True,         # 在控制台显示它在调用什么
    debug_mode=True,  # 启用调试模式
    num_history_runs=5,
    markdown=True,                # 输出漂亮的格式
    add_datetime_to_context=True,
    timezone_identifier="Etc/UTC",  # 可选：指定时区
)

# ==========================================
# Agent OS 初始化
# ==========================================

# Note: AgentOS is created in main.py with both agents
# Run with: uvicorn main:app --host 127.0.0.1 --port 8000
# 创建 AgentOS


# agent_os = AgentOS(
#     agents=[crypto_agent],
# )

# app = agent_os.get_app()

# if __name__ == "__main__":
#     agent_os.serve(app="crypto_agent:app", reload=True)