# 交易 Agent 数据完整性与潜在漏洞审计报告 v2

> **审计范围**: `strategy_context.py`、`analysis/technical.py`、`tools/trading/`、`exchanges/*.py`、`agents/trading_agent.py`、`scheduler.py`
>
> **审计日期**: 2026-04-12

本次审计对报告 v1 中的每一条结论都进行了源码交叉验证，下面列出的是**确认属实**的问题，以及对 v1 中**过度报警/误判**的修正说明。

---

## ✅ 已验证：交易所基类的 Symbol 标准化做得不错

经核实，OKX 和 Bitget 的交易所实现类**已经在底层做了 symbol 标准化**：

| 交易所 | 原始格式 | `_convert_symbol_back()` 输出 |
|--------|---------|------------------------------|
| OKX    | `BTC-USDT-SWAP` | `BTCUSDT` ✅ |
| Bitget | `BTCUSDT` | `BTCUSDT` ✅ |

同样，OKX 的 `get_open_algo_orders()` 已经将其原始的 `conditional` 类型映射为标准的 `TAKE_PROFIT_MARKET` / `STOP_MARKET`（第 572-578 行），Bitget 也将 `planType` 映射为了统一枚举（第 413-421 行）。

**结论：v1 报告中的 §1.2 (Symbol 解析断层) 和 §1.3 (订单类型硬编码) 为误判。** 各交易所实现类在数据出口已经做了统一格式化，`strategy_context.py` 中的 `.replace("USDT", "")` 可以正常工作。

---

## 🔴 确认属实的 BUG

### BUG-1: K 线数据获取强绑定 Binance 公共 API (严重度: 中)

**文件**: `server/analysis/technical.py` L48-99, `server/tools/strategy_context.py` L21-24

**现状**: 所有技术分析（`_fetch_trend`, `_fetch_levels`, `_fetch_volume`, `_fetch_pattern`, `_fetch_volatility`）的 K 线数据源头都是 `_get_binance_klines()`，它直接调用 Binance 的**公共 REST API** (`/api/v3/klines`)，不需要 API 密钥。

**影响评估（降级为"中"）**：
- ⚠️ 对于主流币种（BTC/ETH/SOL/XRP 等），Binance 公共 API 可以获取所有这些币种的行情数据，**即使用户用的是 OKX 交易所也不影响**，因为 K 线是公共市场数据。
- ❌ 但如果用户监控一个**仅在 OKX/Bitget 上市但未在 Binance 上市的币种**（极少见但存在），所有技术分析将返回空数据，Agent 变成盲猜。
- ❌ 在**中国大陆/特定地区**，如果 `BINANCE_API_BASE` 无法连通且用户未配置代理，则所有技术分析全部失效，且无回退。

**修复建议**:
- 短期：在 `_get_current_price()` 失败时，用仓位返回的 `mark_price` 作为 fallback price，避免整个标的被 `continue` 跳过。
- 中期：将 K 线获取解耦为 `get_public_klines(symbol, interval)` 抽象方法，各交易所可以提供自己的公共行情端点做 fallback。

---

### BUG-2: `strategy_context.py` 的 `_get_binance_client_fallback` 未隔离多实例 (严重度: 高)

**文件**: `server/tools/strategy_context.py` L250-337

**现状**: `strategy_context.py` 中有一个独立的 `_get_binance_client_fallback(user_id)` 函数，它的 SQL 是：
```sql
SELECT ti.exchange_account_id
FROM trader_instances ti
WHERE ti.user_id = %s AND ti.exchange_account_id IS NOT NULL
ORDER BY ti.id ASC LIMIT 1
```

**与 `_client.py` 对比**：
`tools/trading/_client.py` 中的 `_get_trading_client()` **已经修复了这个问题**——它优先通过 `get_current_trader_id()` 上下文精确锁定 `trader_instance_id`，只有在取不到时才 fallback 到全局查找。

**但 `strategy_context.py` 中的 `_get_binance_client_fallback` 却是一个完全独立的复制品**，没有使用 `trader_id` 上下文隔离！

**影响**：
- 如果用户同时运行两个 Agent 实例（一个 Binance + 一个 OKX），`_fetch_account()` 和 `_fetch_positions()` 的 fallback 路径会**始终取第一个创建的实例的交易所配置**。
- 这意味着 Agent B（OKX 实例）可能看到 Agent A（Binance 实例）的余额和持仓，基于错误数据做出交易决策。

**修复建议**:
- **删除 `strategy_context.py` 中的 `_get_binance_client_fallback`**，统一使用 `tools/trading/_client.py` 的 `_get_trading_client()` 函数。两套并行的客户端获取逻辑是维护负担和 bug 根源。
- 或者至少将 `trader_instance_id` 传入 `build_strategy_context()` 并透传到 fallback 函数中。

---

### BUG-3: 当前价格获取失败时整个标的被跳过 (严重度: 中)

**文件**: `server/tools/strategy_context.py` L212-215

```python
price = _get_current_price(symbol)
if price is None:
    result["symbols"][symbol] = {"error": "无法获取价格"}
    continue
```

**影响**：
- `_get_current_price()` 只有 5 秒超时，在 API 不稳定时偶尔会失败。
- 一旦某个标的价格获取失败，其**所有技术分析**（趋势、支撑阻力、量能等）都会被跳过。
- Agent 拿到的数据中该标的只有一个 `{"error": "无法获取价格"}`。
- 如果此时 Agent 在该标的上有持仓，它可能会因为"看不到该标的数据"而选择不管理止损止盈。

**修复建议**:
- 在 `_get_current_price` 失败后，尝试用已获取的 `positions` 中对应标的的 `mark_price` 作为 fallback。
- 增加一次简单重试（等 1 秒后再试一次）。

---

### BUG-4: 宏观数据 CoinGecko API 无重试/无缓存 (严重度: 低)

**文件**: `server/tools/strategy_context.py` L554-580

**现状**: `_fetch_macro()` 中对 CoinGecko 的请求只有一个 `try...except`，超时或 429 会导致恐贪指数和 BTC 支配率全部为 `None`。

**影响**：
- Agent 的 L0 分析流程依赖宏观数据来判断大势（如"山寨季"分散风险），但这些数据偶尔会缺失。
- 由于 Agent 被要求在极端恐慌时减少仓位，缺失宏观数据等同于去掉了一道安全阀。

**修复建议**:
- 增加 5 分钟级别的全局缓存，避免高频调用触发限流。
- 如果 API 失败，返回合理的默认值并标记 `"stale": true`，而不是空值。

---

### BUG-5: 技术分析数据膨胀导致 Token 浪费 (严重度: 低)

**文件**: `server/tools/strategy_context.py` L243

**现状**: 输出 JSON 使用 `separators=(",", ":")` 紧凑格式，但所有浮点数保留原始精度（如 `ema21: 83456.23849721`），且每个周期的每个指标都完整输出。

**影响**：
- 5 个标的 × 3 个周期 × 6 个模块 = 大量嵌套 JSON，轻松超过 3000+ tokens。
- LLM 的有效注意力被稀释，在极端情况下可能"遗忘"关键的红线规则（如"不设止损不开仓"）。

**修复建议**:
- 将浮点数 round 到 2-4 位有效数字。
- 设置 token 预算上限，超出时自动裁剪低优先级模块。

---

## 📋 修复优先级排序

| 优先级 | BUG ID | 描述 | 估计工作量 |
|--------|--------|------|-----------|
| P0 | BUG-2 | `strategy_context` 客户端获取独立于交易工具，多实例数据串台 | 1h |
| P1 | BUG-3 | 价格获取失败时标的完全消失 | 30min |
| P2 | BUG-1 | K 线数据无 fallback（极端场景） | 2h |
| P3 | BUG-4 | 宏观数据无缓存无重试 | 30min |
| P3 | BUG-5 | JSON 数据膨胀 | 1h |

---

## 📝 v1 → v2 修正记录

| v1 编号 | v1 结论 | v2 修正 |
|---------|--------|---------|
| §1.2 Symbol 解析断层 | OKX/Bitget 的 symbol 无法匹配 | ❌ **误判**。各交易所实现类的 `_convert_symbol_back()` 已做标准化。 |
| §1.3 订单类型硬编码 | OKX/Bitget 的条件单类型无法识别 | ❌ **误判**。OKX 已映射为 `TAKE_PROFIT_MARKET`/`STOP_MARKET`，Bitget 已映射 `planType`。 |
| §1.1 K线强绑定 | 标记为 Critical | ⬇️ **降级为 Medium**。K线是公共数据，仅影响极少数"Binance 未上市但 OKX 上市"的边缘币种。 |
| §2.1 账户串台 | 标记为 High | ✅ **确认属实**。但问题出在 `strategy_context.py` 的独立 fallback 函数，而非 `_client.py`（后者已修复）。 |
