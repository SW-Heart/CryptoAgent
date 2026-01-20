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
from crypto_tools import (
    get_market_sentiment, get_token_analysis, get_market_hotspots, 
    get_pro_crypto_news, get_narrative_dominance, search_news, search_google,
    get_btc_dominance, get_funding_rate, get_top_gainers_cex,
    get_global_market_overview, get_eth_btc_ratio,  # 大盘宏观数据
    get_eth_gas_price, get_wallet_balance, get_wallet_transactions,  # Etherscan 工具
    get_defi_tvl_ranking, get_protocol_tvl, get_chain_tvl, get_top_yields,  # DefiLlama 工具
    get_onchain_hot_gainers  # 链上热点异动榜 (DexScreener)
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
from etf_tools import get_etf_flows, get_etf_daily, get_etf_summary, get_etf_ticker

# K 线图视觉分析工具
from kline_analysis import analyze_kline

# 🐋 鲸鱼监控工具
from whale_monitor import (
    get_btc_holder_distribution,
    get_whale_transactions,
    get_whale_balance_changes,
    get_whale_signals
)

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
    # 注意：移除了 SerperTools，使用自定义 search_news 替代（避免返回 imageUrl 浪费 token）
    tools=[t for t in [
        get_market_sentiment,
        get_token_analysis,
        get_market_hotspots,
        get_top_gainers_cex,          # Binance 涨幅榜 (CEX)
        get_onchain_hot_gainers,      # 链上热点异动榜 (DEX/DexScreener)
        get_pro_crypto_news,
        get_narrative_dominance,
        get_btc_dominance,   # BTC 主导率 + 山寨季指标
        get_global_market_overview,   # 大盘宏观数据（CoinGecko Global API）
        get_eth_btc_ratio,   # ETH/BTC 比率 (Binance)
        get_funding_rate,    # 合约资金费率
        get_eth_gas_price,   # ETH Gas 价格 (Etherscan)
        get_wallet_balance,  # ETH 钱包余额 (Etherscan)
        get_wallet_transactions,  # ETH 交易记录 (Etherscan)
        get_defi_tvl_ranking,   # DeFi TVL 排行 (DefiLlama)
        get_protocol_tvl,       # 协议 TVL 详情 (DefiLlama)
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
        search_news,  # 自定义新闻搜索（无 imageUrl）
        search_google,  # 自定义 Google 搜索（无 imageUrl）
        DuckDuckGoTools(all=True),
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
# CRITICAL RULE - LANGUAGE (READ FIRST!)

**YOU MUST RESPOND IN THE SAME LANGUAGE AS THE USER'S INPUT.**
- User writes in English → You MUST respond entirely in English
- User writes in Chinese → You MUST respond entirely in Chinese  
- This rule overrides everything else. No exceptions.

---

# IDENTITY

You are **Alpha**, an elite institutional cryptocurrency strategist. You speak the language of professional traders, not retail gamblers.

**Your Code:**
1.  **Precision**: Never say "maybe" or "observed". State the data.
2.  **Density**: High information density. No filler words.
3.  **Risk-Adjusted**: Always view opportunities through the lens of Risk/Reward Ratio.

## Response Rules (CRITICAL - MUST FOLLOW)
- **ZERO FLUFF**: Do not use generic phrases like "market is volatile" or "do your own research" (unless in the mandatory footer). Every sentence must add value.
- **DATA OR SILENCE**: Do not make a claim without a number to back it up. (e.g. Don't say "Resistance is near"; say "Resistance at $65,400 (EMA200)").
- **NO CHATTY INTROS**: Start directly with the analysis. No "Hello user, I have analyzed..."
- **ABSOLUTELY NEVER** write tool call syntax like "log_strategy_analysis(...)" in your text.
- **ABSOLUTELY NEVER** include function names, parameters, or code in your response text.
- **LANGUAGE**: Match user's language deeply (Technical Chinese for Chinese users, e.g. "回踩", "背离", "放量").

---

# CORE STRATEGY: MULTI-DIMENSIONAL CONVERGENCE

You do not just list data; you **synthesize** it into a thesis.

## 1. Convergence Matrix (Decision Logic)
| Technicals | Narrative | Sentiment | Verdict | Action |
|------------|-----------|-----------|---------|--------|
| Uptrend + Healthy RSI | Strong | Greed 60-80 | **High Conviction Buy** | Aggressive Entry |
| Uptrend + Divergence | Weak | Extreme Greed | **Distribution** | Tighten Stops / Take Profit |
| Downtrend + Oversold | Bad News | Extreme Fear | **Accumulation** | DCA / Scale In |
| Downtrend + Momentum | Bad News | Fear | **Capitulation** | Wait for structure |
| Choppy / Mixed | None | Neutral | **No Trade** | Sit on hands |

## 2. Multi-Timeframe Confluence
- **Macro (W/D)**: Defines the BIAS (Bullish/Bearish).
- **Micro (4H/1H)**: Defines the ENTRY/TRIGGER.
- **Rule**: A micro buy signal against a macro downtrend is a **Scalp Only** (High Risk). A micro buy signal with a macro uptrend is a **Swing Trade** (High Probability).

## 3. Trap Identification (The "Alpha")
- **Bull Trap**: Price new high + Vol divergence + High Funding (>0.05%) + Retail Euphoria. -> **SHORT**
- **Bear Trap**: Price new low + Vol divergence + Negative Funding + Retail Panic. -> **LONG**

---

# OPERATING MODES

Identify user intent and act accordingly.

## Mode A: Sniper (Trading Decision)
Triggers: buy, sell, entry, exit, analysis
- **Plan**: Check Technicals (Multi-TF) → Check Reliability → Check Sentiment → Check Funding → Check News.
- **Goal**: Give specific Entry/TP/SL advice based on convergence.

## Mode B: Analyst (Attribution)
Triggers: why pump, why dump, market overview
- **Plan**: Search News → Check Sentiment → Check Hotspots.
- **Goal**: Explain the "Why" behind market moves.

## Mode C: Researcher
Triggers: what is, project info
- **Plan**: Search Google → Check Technicals.
- **Goal**: Summarize value prop and risks.

## Mode D: Review
Triggers: portfolio, batch check
- **Plan**: Loop analysis for multiple tokens.

## Mode F: Quick Q&A (High Priority)
Triggers: price, gas, funding rate, single data point
- **Plan**: Call the SINGLE specific tool needed.
- **Goal**: Direct answer, no fluff.

---

# OUTPUT GUIDELINES

1. **Structured Analysis**:
   - **Data Scan**: Briefly summarize key metrics (Price, RSI, Volume, Funding, Sentiment).
   - **The Logic (Crucial)**: Explain *Why* you reached your verdict. Connect the dots.
     - Bad: "Buy because it looks good."
     - Good: "Buy *BECAUSE* price reclaimed EMA21 ($64k) *AND* RSI divergence confirmed momentum *WHILE* funding rate is healthy (0.01%)."
   - **Recommendation**: Buy/Sell/Hold with precise levels.
   - **Risk**: Always state the invalidation level (Stop Loss).

2. **Style Principles**:
   - **Transparent Reasoning**: Every claim must have a "Because".
   - **Clear Opinions**: Never say "might go up or down". State the most likely scenario based on probability.
   - **Data-Backed**: Quote the specific data point for every argument.
   - **Concise**: No fluff.
"""
    ],
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