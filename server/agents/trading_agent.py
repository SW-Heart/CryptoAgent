"""
Trading Strategy Agent - 专业加密货币合约交易 Agent

该 Agent 具备完整的内置分析框架和执行规范，通过 build_strategy_context()
一次性获取所有分析数据，再根据内置的决策流程做出交易决定。

架构分层：
  L0 内核 — 分析流程、下单规范、风控红线 (固定不变)
  L1 策略 — 用户自定义的策略偏好 prompt_template (可定制)
  L2 参数 — 标的、周期、风险比例、启用的分析模块 (可定制)
"""
import os
from dotenv import load_dotenv
from os import getenv
from agno.agent import Agent
from custom_db import WalSqliteDb as SqliteDb

# Load environment variables
load_dotenv()

# 统一数据引擎 (唯一的数据入口)
from tools.strategy_context import build_strategy_context

# 交易执行工具 (精简集 — 使用交易所无关的通用名称)
from tools.exchange_trading_tools import (
    open_position,
    close_position,
    update_stop_loss,
    update_take_profit,
    place_trailing_stop,
)

# 日志工具
from tools.trading_tools import (
    log_strategy_analysis,
)

# 价格警报工具
from tools.alert_tools import (
    set_price_alert,
    cancel_price_alert,
    list_price_alerts,
)

import time
import functools
import asyncio
from typing import Optional

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
        
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            result_str = str(result)
            result_len = len(result_str)
            print(f"[TokenMonitor] 🟡 FINISHED {tool_name} ({duration:.2f}s) Output: {result_len} chars")
            
            return result
        except Exception as e:
            print(f"[TokenMonitor] 🔴 ERROR in {tool_name}: {e}")
            raise e
    return wrapper

# ==========================================
# 🤖 Agent Factory
# ==========================================

def get_model_instance(provider: str, model_name: str, api_key: str = None, base_url: str = None):
    """Utility to create an Agno model instance based on provider and model name"""
    try:
        if provider == "openai":
            from agno.models.openai import OpenAIChat
            return OpenAIChat(id=model_name or "gpt-4o", api_key=api_key, base_url=base_url)
        elif provider == "deepseek":
            from agno.models.deepseek import DeepSeek
            return DeepSeek(id=model_name or "deepseek-chat", api_key=api_key, base_url=base_url)
        elif provider == "anthropic":
            from agno.models.anthropic import Claude
            return Claude(id=model_name or "claude-4.6-sonnet", api_key=api_key)
        elif provider == "google":
            from agno.models.google import Gemini
            return Gemini(id=model_name or "gemini-3.1-pro", api_key=api_key)
        elif provider in ("custom", "qwen", "glm", "minimax", "kimi"):
            from agno.models.openai import OpenAIChat
            return OpenAIChat(id=model_name, api_key=api_key, base_url=base_url)
        else:
            # Fallback to DeepSeek for custom or unknown
            from agno.models.deepseek import DeepSeek
            return DeepSeek(id="deepseek-chat", api_key=api_key, base_url=base_url)
    except Exception as e:
        print(f"[ModelFactory] Initialization error: {e}")
        return None

def test_llm_connectivity(provider: str, model_name: str, api_key: str) -> tuple[bool, Optional[str]]:
    """
    Tests if the provided LLM configuration is valid by making a minimal call.
    Returns (True, None) if successful, (False, ErrorMessage) otherwise.
    """
    model_instance = get_model_instance(provider, model_name, api_key)
    if not model_instance:
        return False, "Failed to initialize model instance locally"
        
    try:
        print(f"[LLMTest] Testing {provider}/{model_name}...")

        # Use a minimal Agent.run call for compatibility across model providers.
        probe_agent = Agent(
            name="LLMConnectivityProbe",
            model=model_instance,
            tools=[],
            instructions=["Reply with 'ok' only."],
            add_history_to_context=False,
            num_history_runs=0,
            markdown=False,
        )
        run_response = probe_agent.run("ok")
        content = getattr(run_response, "content", None)

        if content and len(str(content).strip()) > 0:
            print(f"[LLMTest] Success: {content}")
            return True, None
        return False, "Received empty response from LLM"
    except Exception as e:
        error_msg = str(e)
        print(f"[LLMTest] Connectivity failure: {error_msg}")
        # Clean up common error messages for better UI display
        if "401" in error_msg or "Unauthorized" in error_msg:
            return False, "Invalid API Key"
        if "404" in error_msg or "not found" in error_msg.lower():
            return False, f"Model '{model_name}' not found by provider"
        if "Rate limit" in error_msg:
            return False, "Rate limit exceeded"
        return False, error_msg

def get_trading_agent(user_id: str, trader_instance_id: int = None) -> Optional[Agent]:
    """
    Factory to create a personalized Trading Agent for a specific user.
    
    如果传入 trader_instance_id，则精确使用该实例绑定的 LLM 和策略配置。
    否则回退到用户的默认 LLM 配置和最新启用的策略（兼容旧调用方式）。
    """
    from binance_client import decrypt_value
    from app.database import get_db_connection as get_db
    import json as _json
    
    llm_config = None
    strategy = None
    strategy_config = {}  # config_json 中的额外配置（含 enabled_modules）
    
    # 1. Fetch LLM & Strategy Profile configurations
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            if trader_instance_id is not None:
                # ===== 精确模式：从 trader_instance 绑定的关系查询 =====
                cursor.execute("""
                    SELECT 
                        lc.provider, lc.model, lc.api_key, lc.base_url,
                        sp.symbols, sp.timeframes, sp.risk_per_trade, 
                        sp.prompt_template, sp.trading_interval, sp.config_json,
                        ti.llm_provider AS ti_llm_provider, ti.llm_model AS ti_llm_model
                    FROM trader_instances ti
                    LEFT JOIN llm_configs lc ON lc.id = ti.llm_config_id
                    LEFT JOIN strategy_profiles sp ON sp.id = ti.strategy_profile_id
                    WHERE ti.id = %s AND ti.user_id = %s
                """, (trader_instance_id, user_id))
                row = cursor.fetchone()
                
                if row:
                    # LLM 配置
                    if row.get("provider") and row.get("api_key"):
                        llm_config = {
                            "provider": row["provider"],
                            "model": row["model"],
                            "api_key": row["api_key"],
                            "base_url": row.get("base_url"),
                        }
                    else:
                        print(f"[AgentFactory] Trader #{trader_instance_id}: No bound llm_config, falling back to user default")
                        cursor.execute("""
                            SELECT provider, model, api_key, base_url
                            FROM llm_configs 
                            WHERE user_id = %s AND is_default = TRUE
                            LIMIT 1
                        """, (user_id,))
                        llm_config = cursor.fetchone()
                    
                    # 策略配置
                    if row.get("symbols"):
                        strategy = {
                            "symbols": row["symbols"],
                            "timeframes": row["timeframes"],
                            "risk_per_trade": row["risk_per_trade"],
                            "prompt_template": row["prompt_template"],
                            "trading_interval": row["trading_interval"],
                        }
                        # 解析 config_json 中的 enabled_modules
                        raw_config = row.get("config_json")
                        if raw_config:
                            if isinstance(raw_config, str):
                                try:
                                    strategy_config = _json.loads(raw_config)
                                except Exception:
                                    strategy_config = {}
                            elif isinstance(raw_config, dict):
                                strategy_config = raw_config
                else:
                    print(f"[AgentFactory] Trader instance #{trader_instance_id} not found for user {user_id[:8]}")
            
            # ===== 回退模式 =====
            if not llm_config:
                cursor.execute("""
                    SELECT provider, model, api_key, base_url
                    FROM llm_configs 
                    WHERE user_id = %s AND is_default = TRUE
                    LIMIT 1
                """, (user_id,))
                llm_config = cursor.fetchone()
            
            if not strategy:
                cursor.execute("""
                    SELECT symbols, timeframes, risk_per_trade, prompt_template, 
                           trading_interval, config_json
                    FROM strategy_profiles
                    WHERE user_id = %s AND is_enabled = TRUE
                    ORDER BY updated_at DESC LIMIT 1
                """, (user_id,))
                fallback = cursor.fetchone()
                if fallback:
                    strategy = dict(fallback)
                    raw_config = fallback.get("config_json")
                    if raw_config:
                        if isinstance(raw_config, str):
                            try:
                                strategy_config = _json.loads(raw_config)
                            except Exception:
                                strategy_config = {}
                        elif isinstance(raw_config, dict):
                            strategy_config = raw_config
    except Exception as e:
        print(f"[AgentFactory] Database error: {e}")
        return None
    finally:
        conn.close()
        
    if not llm_config:
        print(f"[AgentFactory] No LLM config found for user {user_id[:8]} (trader_instance={trader_instance_id})")
        return None

    # Handle missing strategy with defaults
    if not strategy:
        strategy = {
            "symbols": "BTC,ETH",
            "timeframes": "1h,4h",
            "risk_per_trade": 0.02,
            "prompt_template": "Focus on trend following strategy with strict risk management.",
            "trading_interval": 60,
        }
        
    provider = llm_config.get("provider", "deepseek")
    model_name = llm_config.get("model", "deepseek-chat")
    api_key_raw = llm_config.get("api_key")
    base_url = llm_config.get("base_url")
    
    # Decrypt key
    api_key = api_key_raw
    if api_key_raw and api_key_raw.startswith("gAAAA"):
        try:
            api_key = decrypt_value(api_key_raw)
        except Exception as e:
            print(f"[AgentFactory] Decryption failed for user {user_id}: {e}")
    
    # 2. Get model instance
    model_instance = get_model_instance(provider, model_name, api_key, base_url)
    if not model_instance:
        print(f"[AgentFactory] Failed to create model instance for {provider}")
        return None

    # 3. 从 config_json 中获取启用的分析模块
    from tools.strategy_context import get_default_enabled_modules
    enabled_modules = strategy_config.get("enabled_modules", get_default_enabled_modules())
    modules_str = ",".join(enabled_modules) if isinstance(enabled_modules, list) else str(enabled_modules)

    symbols = strategy.get("symbols", "BTC,ETH")
    timeframes = strategy.get("timeframes", "1h,4h")
    risk_pct = strategy.get("risk_per_trade", 0.02)

    # 3.5 从 config_json 中获取可配置交易规则（向后兼容：无 trading_rules 时使用默认值）
    rules = strategy_config.get("trading_rules", {})
    signal_min_dims = rules.get("signal_min_dimensions", 3)
    allow_weak      = rules.get("allow_weak_signal", False)
    max_pos_pct     = rules.get("max_position_pct", 20)
    vol_reduce      = rules.get("volatility_reduce", True)
    sl_buffer_pct   = rules.get("sl_buffer_pct", 0.5)
    breakeven_r     = rules.get("breakeven_at_r", 1.0)
    trail_r         = rules.get("trail_at_r", 2.0)
    leverage        = rules.get("default_leverage", 10)
    entry_standards = rules.get("entry_standards", "")
    pos_management  = rules.get("position_management", "")

    # 计算止损乘数
    sl_long_factor  = round(1 - sl_buffer_pct / 100, 4)   # e.g. 0.995
    sl_short_factor = round(1 + sl_buffer_pct / 100, 4)   # e.g. 1.005

    # 弱信号处理文本
    weak_signal_text = "不开仓，记录 HOLD" if not allow_weak else "可用50%仓位试探性开仓"

    # 高波动处理文本
    vol_reduce_text = "高波动 (volatility.status=\"extreme_high\") 时再减半" if vol_reduce else "高波动环境不额外减仓"

    # 4. 构建完整 System Prompt（固定基础设施 + 可配交易规则 + 用户偏好）
    dynamic_instructions = [f"""
# 加密货币合约交易 Agent

你是一个专业的加密货币合约交易 Agent。你擅长技术分析和风险管理，
能够自主地分析市场数据并做出交易决策。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 当前实例参数 [强制执行]
- **监控标的**: {symbols}
- **分析周期**: {timeframes}
- **单笔风险**: {risk_pct * 100}% of Balance
- **启用模块**: {modules_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 标准分析流程 [必须按顺序执行]

### Step 1: 获取全部数据
调用唯一的数据工具，一次性获取所有分析数据：
```
build_strategy_context()
```
返回的 JSON 中包含：account(余额)、positions(持仓)、open_orders(当前挂单)、
exchange_constraints(交易所合约限制)、macro(宏观)、funding(费率) 以及各标的的技术指标数据。

### Step 2: 确认账户状态 [关键反重复步骤]
- 检查 account.available (可用余额)
- 检查 positions.list (已有持仓及方向)
- **⚠️ 检查 exchange_constraints**（如果存在）:
  - 该字段显示你所用交易所每个币种的最小开仓保证金
  - 例如 exchange_constraints.BTC.min_margin_by_leverage["10x"] = 77.0 表示 10 倍杠杆下 BTC 最低需要 77 USDT 保证金
  - **如果你的 margin 计算值低于该最低要求 → 直接 HOLD，不要尝试开仓**
- **⚠️ 重点检查每个持仓的 existing_tp_orders 和 existing_sl_orders 字段**
  - 如果 existing_sl_orders 已有止损挂单 → 禁止再挂新止损，使用 update_stop_loss 调整价格
  - 如果 existing_tp_orders 已有止盈挂单 → 禁止再挂新止盈，使用 update_take_profit 调整价格
  - **例外**：阶段性止盈（TP1/TP2/TP3 按不同仓位比例分批止盈）允许存在多个 TP 订单
- 如果已有同方向同标的仓位 → 不重复开仓，考虑调整止损/止盈
- 检查 open_orders.list 确认全局挂单状态

### Step 3: 多维度信号评估
对每个标的，综合以下维度判断：
- **趋势**: trend.direction + trend.strength + trend.major_trend (多周期加权)
- **关键位**: levels.nearest_support / nearest_resistance (优先 EMA/Vegas)
- **量能**: volume.ratio + volume.divergence + volume.flow (辅助)
- **形态**: pattern.name + pattern.bias (辅助)
- **波动**: volatility.status (决定仓位大小和止损宽度)

### Step 3.5: 顺大逆小检查 [最高优先级 - 强制执行]

**核心原则：大周期定方向，小周期找入场。**

⛔ **否决权 (trend.veto)**:
- 如果 trend.veto = "no_long" → 🚫 **绝对禁止做多**，只允许做空或 HOLD
- 如果 trend.veto = "no_short" → 🚫 **绝对禁止做空**，只允许做多或 HOLD
- 否决权来自 1d+1w 的 EMA 排列 + Vegas 通道位置（首要指标），不可被任何其他信号覆盖

📐 **大周期趋势 (trend.major_trend)**:
- major_trend = "bearish" → 大级别空头结构。小周期(4h/1h/15m)的看涨信号只是下跌中继反弹，不开多。
- major_trend = "bullish" → 大级别多头结构。小周期的回调是入场机会，不做空。
- major_trend = "neutral" → 无明确方向，可两方向操作但需更强信号。

### Step 4: 信号强度评估

🟢 **强信号** (可按风险比例正常开仓):
- trend.direction 一致且 strength="strong"
- trend.veto 不冲突（顺大逆小通过）
- 价格接近 **EMA/Vegas 关键位** (nearest_support/resistance 的 dist_pct < 2%)
- volume.flow 配合方向 (做多时 inflow / 做空时 outflow)
- {signal_min_dims}个以上维度方向一致

🟡 **中等信号** (减半仓位):
- {max(1, signal_min_dims - 1)}个维度方向一致
- 价格接近但未到 EMA/Vegas 关键位
- ⚠️ 如果 nearest_support/resistance 的 source 是 Fib 开头（如 Fib_0.618）表示支撑来自 Fibonacci 而非 EMA/Vegas，**需要更多确认条件才可开仓**（至少需要量能配合 volume.flow）

🔴 **弱信号 / 无信号** ({weak_signal_text}):
- 趋势 direction="neutral" 或各维度矛盾
- 量能 divergence="bearish" 与趋势冲突
- 价格远离所有关键位
- ⚠️ trend.veto 冲突（想做多但 veto="no_long"）→ 直接 HOLD

{f'''### 自定义入场标准
{entry_standards}
''' if entry_standards else ''}
### Step 5: 下单执行规范

1. **仓位计算**:
   - margin = account.available × {risk_pct}
   - 绝对不超过 available 的 {max_pos_pct}%
   - {vol_reduce_text}
   - 📊 **量能调节**: 如果 volume.ratio < 0.5 (极低量能) → 仓位再减半
   - 😱 **情绪调节**: 如果 macro.fng < 20 (极端恐惧) → 仓位再减半
   - ⚠️ **最低保证金校验**：如果 exchange_constraints 中该标的存在 min_margin_by_leverage,
     必须确保你计算的 margin >= min_margin_by_leverage[当前杠杆]。
     如果不够 → 直接 HOLD 该标的，不要尝试开仓，不要提高杠杆来凑。

2. **止损设置 [强制]**:
   - LONG: 止损 = nearest_support.price × {sl_long_factor} (支撑位下方{sl_buffer_pct}%)
   - SHORT: 止损 = nearest_resistance.price × {sl_short_factor} (阻力位上方{sl_buffer_pct}%)
   - 如果没有明确的支撑/阻力位 → 使用 volatility.sl_suggest
   - **没有止损 = 不开仓**

3. **止盈参考**:
   - LONG 止盈: nearest_resistance.price 附近
   - SHORT 止盈: nearest_support.price 附近

4. **开仓调用**:
   open_position(symbol=标的, direction=方向, margin=计算值,
                 leverage={leverage}, stop_loss=止损价, take_profit=止盈价)
   - ⚠️ 如果收到 "insufficient to buy 1 contract" 错误 → 停止重试，记录 HOLD。

### Step 6: 持仓管理

已有持仓时的处理规则：
- **同方向已有仓**: 不重复开仓，检查是否应移动止损或止盈
  - 盈利 > {breakeven_r}倍风险 → update_stop_loss 到成本价 (保本)
  - 盈利 > {trail_r}倍风险 → update_stop_loss 到 +1R 位置
  - 如需调整止盈价 → 使用 update_take_profit（不要新挂 TP 单）
- **反方向强信号**: 先 close_position 平现仓，再开新仓
- **持仓亏损中**: 只要未触及止损线则持有，不手动平仓
{f'''
### 自定义持仓管理规则
{pos_management}
''' if pos_management else ''}
### Step 7: 止盈止损管理 [严格执行]

- **全仓止盈/止损**：每个仓位最多只允许存在 1 个 TP 和 1 个 SL 挂单
  - 不得重复创建，只能用 update_stop_loss / update_take_profit 修改价格
- **阶段性止盈 (TP1/TP2)**：可以为同一仓位设置多个不同数量的 TP 订单
  - 例如：TP1 平仓 50% 在价位 A，TP2 平仓剩余 50% 在价位 B
  - 使用 open_position 开仓时的 take_profit 设 TP1，然后额外挂 TP2

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 用户自定义策略偏好
{strategy.get('prompt_template', 'Focus on trend following strategy with strict risk management.')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 价格警报管理 [每次分析后执行]

你有能力自主设置关键价格位的警报。当价格到达你设置的位置时，系统会自动触发一次分析。

### 查看已有警报
- 在 build_strategy_context() 返回的 alerts 段可以看到你设置的所有活跃警报
- 每次分析时检查是否有已失效或不再需要的警报，及时用 cancel_price_alert() 清理

### 设置新警报
分析完成后，如果发现重要的关键价位，使用 set_price_alert() 设置监控：
- 重要的支撑/阻力位（EMA/Vegas 关键位）
- 突破/跌破确认位
- 止损保护位、止盈目标位附近
- 每用户最多 10 个活跃警报，请合理分配

### 取消警报
- 当持仓已变化或市场结构改变，之前的关键价位不再有效时，及时取消
- 可按 alert_id 精确取消，或按 symbol 批量取消

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 日志记录 [每次执行必须]

无论是否有操作，都必须调用 log_strategy_analysis() 记录：
- market_analysis: 趋势判断 + 关键价位 + 量能状态
- position_check: 当前持仓 + 余额
- strategy_decision: 完整的决策逻辑推理过程
- action_taken: HOLD / OPEN_LONG / OPEN_SHORT / CLOSE / ADJUST_SL

## 禁止行为 [红线]
- ❌ 禁止在 {symbols} 以外的标的开仓
- ❌ 禁止不设止损的开仓
- ❌ 禁止单笔 margin 超过可用余额的 {max_pos_pct}%
- ❌ 禁止忽略已有持仓直接反向开仓（必须先平仓）
- ❌ 禁止在 trend.direction="neutral" 且无明确信号时开仓
- ❌ **禁止在 trend.veto="no_long" 时做多**（大周期空头否决，即使小周期看涨也不可以）
- ❌ **禁止在 trend.veto="no_short" 时做空**（大周期多头否决，即使小周期看跌也不可以）
- ❌ 禁止在 existing_sl_orders 非空时再新增全仓止损单（应使用 update_stop_loss 修改价格）
- ❌ 禁止在 existing_tp_orders 非空时再新增全仓止盈单（应使用 update_take_profit 修改价格，阶段性分批止盈除外）
"""]

    # 5. 为所有工具预绑定 user_id，确保 LLM 调用时自动使用正确的用户身份
    #    使用闭包而非 partial，让 Agno 看到的签名中不含 user_id 参数
    from tools.trading_tools import set_current_user
    set_current_user(user_id)  # 同时设置 ContextVar 作为备份
    
    _uid = user_id  # 闭包捕获
    
    def _build_strategy_context() -> str:
        """一次性构建 Agent 策略分析所需的全部上下文数据（基于策略配置的预设参数）。"""
        return build_strategy_context(symbols=symbols, timeframes=timeframes, enabled_modules=modules_str, user_id=_uid)
    
    def _open_position(symbol: str, direction: str, margin: float, leverage: int = 10, stop_loss: float = None, take_profit: float = None) -> dict:
        """在 Binance 合约开仓。"""
        return open_position(symbol=symbol, direction=direction, margin=margin, leverage=leverage, stop_loss=stop_loss, take_profit=take_profit, user_id=_uid)
    
    def _close_position(symbol: str, close_percent: float = 100) -> dict:
        """平仓指定标的的持仓。"""
        return close_position(symbol=symbol, close_percent=close_percent, user_id=_uid)
    
    def _update_stop_loss(symbol: str, new_stop_loss: float) -> dict:
        """更新指定标的的止损价格。"""
        return update_stop_loss(symbol=symbol, new_stop_loss=new_stop_loss, user_id=_uid)
    
    def _place_trailing_stop(symbol: str, callback_rate: float = 1.0, activation_price: float = None) -> dict:
        """设置追踪止损。"""
        return place_trailing_stop(symbol=symbol, callback_rate=callback_rate, activation_price=activation_price, user_id=_uid)

    def _update_take_profit(symbol: str, new_take_profit: float) -> dict:
        """更新指定标的的止盈价格（只替换现有 TP 订单，不影响 SL）。"""
        return update_take_profit(symbol=symbol, new_take_profit=new_take_profit, user_id=_uid)

    # 价格警报工具闭包
    def _set_price_alert(symbol: str, target_price: float, direction: str, reason: str = "") -> dict:
        """设置价格警报。当价格到达目标位时自动触发一次策略分析。direction 为 'ABOVE'(上穿) 或 'BELOW'(下穿)。"""
        return set_price_alert(symbol=symbol, target_price=target_price, direction=direction, reason=reason, user_id=_uid)

    def _cancel_price_alert(alert_id: int = None, symbol: str = None) -> dict:
        """取消价格警报。提供 alert_id 取消单个，或提供 symbol 取消该标的所有警报。"""
        return cancel_price_alert(alert_id=alert_id, symbol=symbol, user_id=_uid)

    def _list_price_alerts() -> dict:
        """列出当前所有活跃的价格警报。"""
        return list_price_alerts(user_id=_uid)

    # 6. Create Agent instance
    return Agent(
        name="TradingStrategy",
        id=f"ts-{user_id[:8]}",
        model=model_instance,
        tools=[monitor_tool_usage(t) for t in [
            _build_strategy_context,  # 📥 唯一数据入口 (user_id 已绑定)
            _open_position,           # 📤 开仓 (user_id 已绑定)
            _close_position,          # 📤 平仓 (user_id 已绑定)
            _update_stop_loss,        # 📤 调整止损 (user_id 已绑定)
            _update_take_profit,      # 📤 调整止盈 (user_id 已绑定)
            _place_trailing_stop,     # 📤 追踪止损 (user_id 已绑定)
            _set_price_alert,         # 🔔 设置价格警报 (user_id 已绑定)
            _cancel_price_alert,      # 🔕 取消价格警报 (user_id 已绑定)
            _list_price_alerts,       # 📋 查看价格警报 (user_id 已绑定)
            log_strategy_analysis,    # 📝 日志记录
        ]],
        instructions=dynamic_instructions,
        db=SqliteDb(session_table=f"ts_{user_id[:8]}", db_file=f"tmp/ts_{user_id[:8]}.db"),
        add_history_to_context=False,
        num_history_runs=0,
        markdown=True,
        add_datetime_to_context=True,
        timezone_identifier="Etc/UTC",
        debug_mode=True,
    )

