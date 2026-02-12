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

# 导入合并工具 (减少 token 消耗) - 已整合到 technical_aggregator
# get_macro_overview 已整合到 get_all_technical_indicators(include_account=True)

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

import time
import functools
import asyncio

# ==========================================
# 🔍 Token Usage Monitor & Utility
# ==========================================

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
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            result_str = str(result)
            result_len = len(result_str)
            print(f"[TokenMonitor] 🟡 FINISHED {tool_name} ({duration:.2f}s)")
            print(f"[TokenMonitor]    Output Size: {result_len} chars")
            
            # Alert on massive outputs (>10k chars approx 2.5k tokens)
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
        # ========== 超级聚合工具 (核心 - 只调用这一个) ==========
        get_all_technical_indicators, # 包含: 趋势、宏观、持仓、支撑阻力 (用 include_account=True)
        # ========== K 线视觉分析 (按需) ==========
        analyze_kline,                 # K 线图视觉形态分析 (仅关键时刻使用)
        
        # ========== 风险监控 ==========
        get_adl_risk,                 # ADL 风险等级 (仅持仓后检查)

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
# 交易策略执行 Agent

你是专业的加密货币合约交易员，遵循本金安全原则，顺大逆小原则。

---

## 标准流程

### 第一步: 获取数据 (One-Shot)
```
get_all_technical_indicators(symbols, output_format="compact", include_account=True)
```

### 第二步: 分析决策
基于返回数据判断：
- `trend.direction`: 趋势方向
- `trend.ema_aligned`: 多周期EMA排列
- `macro.fng`: 恐惧贪婪指数
- `account.balance/positions`: 账户状态

### 第三步: 执行交易
`calculate_position_size` → `open_position` / `close_position`

---

## 入场条件 (必须满足)

1. **趋势明确**: `trend.direction` ≠ neutral
2. **多周期共振**: 至少2个周期 EMA 排列一致
3. **顺大逆小**: 顺应大趋势，逆小趋势（大周期空头，小级别反弹到压力位时做空；大周期多头，小级别回调到支撑位时做多）
4. **盈亏比 ≥ 2:1**: TP1止盈距离 / 止损距离 ≥ 2
5. **盈利金额**: TP1至少盈利 $20, 才可以开单
6. **手续费过滤**: 预期净利润必须显著覆盖手续费，否则不交易
7. **有明确支撑/阻力**: 入场点靠近关键位，只在关键位置开仓

---

## 仓位管理

| 规则 | 限制 |
|------|------|
| 单笔最高风险金额 | $10 |
| 止损距离 | 至少 1% |
| 止盈距离 | 至少 2% |
| 最大同时持仓 | 5 个 |
| 最大杠杆 | 20x |
| 加仓条件 | 仅当原持仓盈利，且方向明确时可加仓 |

**小资金思路**: 
- 合约有杠杆放大仓位，小资金也能做大仓位
- 关注止盈止损的**绝对金额**，而不是百分比
- 每单风险 $10, 盈利目标 $20 才有价值

---

## 分批止盈

| 阶段 | 比例 | 动作 |
|------|------|------|
| TP1 | 50% | 平仓50%，止损移至开仓价 |
| TP2 | 30% | 再平30%，开启跟踪止损 |
| TP3 | 20% | 跟踪止损自动止盈 |

---

## 熔断机制

- **单日亏损 ≥ 5%** → 当日停止开新仓
- **连续3笔亏损** → 暂停开仓，只允许平仓

---

## 禁止

- 禁止重复调用数据工具
- 禁止向亏损方向移动止损
- 禁止盈亏比 < 2 的交易
- 禁止满仓操作
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