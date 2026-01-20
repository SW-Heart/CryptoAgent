"""
Swap Agent - DEX 交易执行 Agent

专门处理链上交易意图的 AI Agent。
接收用户自然语言指令（如"购买 1000U 的 BTC"），
解析意图并生成 A2UI 交易卡片供前端渲染。
"""

import os
from dotenv import load_dotenv
from os import getenv
from agno.agent import Agent
from agno.models.deepseek import DeepSeek
from custom_db import WalSqliteDb as SqliteDb

# Load environment variables
load_dotenv()

LLM_KEY = getenv("OPENAI_API_KEY")

# 导入交易工具
from swap_tools import get_swap_quote, generate_swap_a2ui


# ==========================================
# Swap Agent
# ==========================================

swap_agent = Agent(
    name="SwapAgent",
    id="swap-agent",
    model=DeepSeek(id="deepseek-chat", api_key=LLM_KEY),
    
    # 工具集
    tools=[
        get_swap_quote,      # 获取交易报价
        generate_swap_a2ui,  # 生成 A2UI 交易卡片
    ],
    
    # 系统指令
    instructions="""
# IDENTITY

You are **SwapBot**, a silent DEX trading execution agent. Your ONLY job is to call tools - you should output MINIMAL text.

# CRITICAL RULE: MINIMAL OUTPUT

用简单直接的语言解释要做什么，不要说废话

Your ONLY output should be:
1. Call `generate_swap_a2ui(from_token, to_token, amount)` - THAT'S IT!
2. After the tool completes, say ONLY: "交易卡片已生成，请确认后执行。" (ONE short sentence)

# TRADE PARSING

Parse user intent and map to tokens:
- "U" / "刀" / "美金" = USDT
- "BTC" / "比特币" = WBTC
- "ETH" / "以太坊" = WETH
- "购买 1000U 的 BTC" → from=USDT, to=WBTC, amount=1000

# WORKFLOW

1. Parse command → identify from_token, to_token, amount
2. Call `generate_swap_a2ui(from_token, to_token, amount)`
3. Output: "交易卡片已生成，请确认后执行。"

THAT'S ALL. No greetings, no explanations, no summaries.

# ERROR HANDLING

If parsing fails, say: "抱歉，无法识别交易指令。请使用格式如：购买1000U的ETH"
""",
    
    db=SqliteDb(session_table="test_agent", db_file="tmp/test.db"),
    add_history_to_context=True,
    debug_mode=True,
    num_history_runs=3,
    markdown=True,
    add_datetime_to_context=True,
    timezone_identifier="Etc/UTC",
)


# ==========================================
# 测试
# ==========================================

if __name__ == "__main__":
    # 测试 Agent
    response = swap_agent.run("购买 1000U 的 BTC")
    print(response.content)
