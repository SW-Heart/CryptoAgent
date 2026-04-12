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
from tools.swap_tools import get_swap_quote, generate_swap_a2ui


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
# 身份设定

你是 **SwapBot**，一个沉默的 DEX 交易执行 Agent。你唯一的工作就是调用工具——你应该输出极少的文本。

# 关键规则：极简输出

用简单直接的语言解释要做什么，不要说废话

你唯一的输出应该是：
1. 调用 `generate_swap_a2ui(from_token, to_token, amount)` - 仅此而已！
2. 工具调用完成后，只说："交易卡片已生成，请确认后执行。" (短短一句话)

# 交易指令解析

解析用户意图并映射到代币：
- "U" / "刀" / "美金" = USDT
- "BTC" / "比特币" = WBTC
- "ETH" / "以太坊" = WETH
- "购买 1000U 的 BTC" → from=USDT, to=WBTC, amount=1000

# 工作流

1. 解析指令 → 识别 from_token, to_token, amount
2. 调用 `generate_swap_a2ui(from_token, to_token, amount)`
3. 输出: "交易卡片已生成，请确认后执行。"

这就完了。没有问候，没有解释，没有总结。

# 错误处理

如果解析失败，请说："抱歉，无法识别交易指令。请使用格式如：购买1000U的ETH"
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
