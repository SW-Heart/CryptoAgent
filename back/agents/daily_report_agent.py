"""
Daily Position Report Agent - 每日持仓情况速递

简化版日报，专注于持仓汇报和后续规划。
"""
import os
from dotenv import load_dotenv
from os import getenv
from agno.agent import Agent
from agno.models.deepseek import DeepSeek

# 使用 Binance 持仓工具
from tools.binance_trading_tools import binance_get_positions_summary

load_dotenv()
LLM_KEY = getenv("OPENAI_API_KEY")

daily_report_agent = Agent(
    name="DailyPositionReporter",
    id="daily-report-agent",
    model=DeepSeek(id="deepseek-chat", api_key=LLM_KEY),
    tools=[
        binance_get_positions_summary
    ],
    instructions=["""
# 每日持仓速递

你是持仓汇报员，生成简洁的每日持仓情况报告。所有输出必须使用中文。

## 流程

1. 调用 `binance_get_positions_summary()` 获取持仓数据
2. 生成 Markdown 表格展示

## 输出格式

### 📊 每日持仓速递 | [日期]

#### 💰 账户概览
- 可用余额: $XXX
- 当日盈亏: +/-$XXX

#### 📈 当前持仓

| 币种 | 方向 | 仓位 | 入场价 | 现价 | 盈亏 | ROI |
|------|------|------|--------|------|------|-----|
| BTC | 多 | $XXX | $XXX | $XXX | +$XX | +X% |

#### 🎯 后续规划
- [基于当前持仓的简要操作建议]

---

## 规则
1. 如无持仓，显示"当前无持仓"
2. 表格数据必须来自工具返回
3. 保持简洁，不要冗长分析
4. 所有内容使用中文
"""],
    markdown=True,
    add_datetime_to_context=True,
    timezone_identifier="Etc/UTC",
)
