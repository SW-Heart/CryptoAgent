---
name: exchange_integration
description: 加密货币交易所接入规范 — 统一接口、字段映射、防坑指南与逐步集成清单
---

# 交易所集成 Skill

> **适用场景**: 当需要接入新的加密货币交易所（如 Bybit、Gate.io、Bitget 等）时，按照本文档的规范进行开发，可以避免重复踩坑。

---

## 1. 系统架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                     Frontend (React)                            │
│                   ExecutionPage.jsx                              │
│  消费统一字段: amount, type, quantity, symbol, direction ...     │
└──────────────────────────┬──────────────────────────────────────┘
                           │  HTTP API
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              Backend Router (FastAPI)                            │
│            app/routers/strategy.py                               │
│  职责: 路由分发 + 部分字段二次格式化 + 本地DB Fallback           │
│  端点: /wallet, /positions, /orders, /trade-history,            │
│        /position-history, /income-history, /funding-rate ...    │
└──────────────────────────┬──────────────────────────────────────┘
                           │  调用统一接口
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              Exchange Factory                                    │
│            exchange_factory.py                                   │
│  职责: 根据 provider 名称创建对应的客户端实例                     │
│  输入: provider="binance"|"okx"|"bybit"...                      │
│  输出: ExchangeClient 子类实例                                   │
└────────┬────────────────────────────┬───────────────────────────┘
         │                            │
         ▼                            ▼
┌─────────────────┐        ┌─────────────────┐
│ BinanceFutures  │        │  OKXFutures     │
│ Client          │        │  Client         │
│ binance_client  │        │  exchange_okx   │
│ .py             │        │  .py            │
│                 │        │                 │
│ 继承             │        │ 继承            │
│ ExchangeClient  │        │ ExchangeClient  │
│ (exchange_base) │        │ (exchange_base) │
└─────────────────┘        └─────────────────┘
```

### 关键文件路径

| 文件 | 职责 |
|------|------|
| `back/exchange_base.py` | 抽象基类，定义所有交易所必须实现的统一接口 |
| `back/exchange_factory.py` | 工厂方法，根据 provider 名称创建客户端实例 |
| `back/binance_client.py` | Binance Futures 客户端实现 |
| `back/exchange_okx.py` | OKX Futures (SWAP) 客户端实现 |
| `back/app/routers/strategy.py` | 所有交易数据的 API 路由层 |
| `back/tools/binance_trading_tools.py` | Agent 工具函数（开仓/平仓/查询） |
| `back/tools/trading_tools.py` | 统一交易工具分发层 |
| `agno-chat-ui/src/pages/ExecutionPage.jsx` | 前端控制台页面 |

---

## 2. 统一字段规范（核心契约）

> **铁律**: 每个交易所客户端方法返回的数据**必须**使用以下统一字段名。  
> **绝不允许**将交易所原始 API 的字段名直接透传给上层。

### 2.1 余额 `get_usdt_balance()` → `dict`

```python
{
    "wallet_balance": float,      # 钱包总余额 (USDT)
    "available_balance": float,   # 可用余额
    "margin_balance": float,      # 保证金余额 (含未实现盈亏)
    "unrealized_pnl": float,      # 总未实现盈亏
    "assets": [                   # 各资产明细
        {
            "asset": "USDT",
            "walletBalance": float,
            "marginBalance": float,
            "unrealizedProfit": float,
            "availableBalance": float
        }
    ]
}
```

### 2.2 持仓 `get_positions()` → `List[dict]`

```python
{
    "symbol": "BTCUSDT",          # 统一格式: 基础币+USDT（不要带 -SWAP 等后缀）
    "direction": "LONG" | "SHORT",
    "quantity": float,            # 持仓数量（**正数**, 方向已由 direction 表示）
    "entry_price": float,         # 开仓均价
    "mark_price": float,          # 标记价格
    "unrealized_pnl": float,      # 未实现盈亏
    "leverage": int,              # 杠杆倍数
    "margin_type": "cross" | "isolated",
    "liquidation_price": float    # 强平价格
}
```

> ⚠️ **坑点**: OKX 的 `symbol` 原始格式为 `BTC-USDT-SWAP`，必须转换为 `BTCUSDT`。  
> ⚠️ **坑点**: OKX 的数量以 "张数" (contracts) 为单位，必须乘以 `ctVal`（合约面值）转换为 base coin 数量。

### 2.3 普通挂单 `get_open_orders()` → `List[dict]`

```python
{
    "orderId": str | int,         # 订单ID
    "symbol": "BTCUSDT",
    "side": "BUY" | "SELL",       # 全大写
    "type": "LIMIT" | "MARKET",   # 全大写
    "origQty": float,             # 挂单数量
    "executedQty": float,         # 已成交数量
    "price": float,               # 挂单价格
    "avgPrice": float,            # 成交均价
    "reduceOnly": bool,           # 是否仅平仓
    "closePosition": str,         # "true" | "false"
    "status": "NEW" | "PARTIALLY_FILLED",
    "time": int,                  # 毫秒时间戳
    "updateTime": int
}
```

### 2.4 条件单（算法单） `get_open_algo_orders()` → `List[dict]`

```python
{
    "algoId": str,                # 算法订单ID
    "orderId": str,               # 与 algoId 相同（方便UI统一处理）
    "symbol": "BTCUSDT",
    "side": "BUY" | "SELL",
    "type": "CONDITIONAL",        # 固定为 CONDITIONAL
    "algoType": "STOP_MARKET" | "TAKE_PROFIT_MARKET" | "CONDITIONAL",
    "origQty": float,             # 数量（全仓平仓时可能为 0）
    "triggerPrice": float,        # 触发价格
    "stopPrice": float,           # 与 triggerPrice 相同（兼容）
    "reduceOnly": bool,
    "status": "NEW" | "WORKING",
    "time": int
}
```

> ⚠️ **巨坑**: Binance 的止盈止损市价单 `origQty` 为 `"0"` 当使用 `closePosition=true`（全部平仓）模式。  
> Router 层有智能补偿: 从本地 `positions` 表反查当前持仓数量来填补。

### 2.5 成交历史 `get_trade_history()` → `List[dict]`

```python
{
    "id": int | str,              # 成交ID
    "symbol": "BTCUSDT",
    "orderId": str | int,         # 关联订单ID
    "side": "BUY" | "SELL",
    "price": float,               # ❗ 必须是 float，不是字符串
    "qty": float,                 # ❗ 必须是 float
    "realizedPnl": float,         # 已实现盈亏
    "commission": float,          # 手续费（通常为负数）
    "commissionAsset": "USDT",    # 可选
    "time": int,                  # 毫秒时间戳
    "positionSide": str,          # 可选: "LONG" | "SHORT" | "BOTH"
    "maker": bool                 # 可选: 是否为 Maker
}
```

> ✅ **已修复**: Binance 客户端所有方法已在客户端层完成格式化，`price`/`qty` 等统一返回 `float` 类型。  
> **规则**: 新交易所务必在客户端层完成类型转换，不可透传原始 API 数据。

### 2.6 订单历史 `get_order_history()` → `List[dict]`

```python
{
    "orderId": str | int,
    "symbol": "BTCUSDT",
    "side": "BUY" | "SELL",
    "type": "LIMIT" | "MARKET" | "STOP_MARKET" | ...,
    "origQty": float,
    "executedQty": float,
    "price": float,
    "avgPrice": float,
    "reduceOnly": bool,
    "status": "FILLED" | "CANCELED" | "EXPIRED",
    "time": int,
    "updateTime": int
}
```

### 2.7 资金流水 `get_income_history()` → `List[dict]`

```python
{
    "symbol": "BTCUSDT",          # 可能为空
    "type": "REALIZED_PNL" | "FUNDING_FEE" | "COMMISSION" | "TRANSFER" | ...,
    "amount": float,              # ❗ 金额，不是 income！
    "asset": "USDT",
    "time": int,                  # 毫秒时间戳
    "info": str                   # 备注（可选）
}
```

> ⚠️ **血泪教训**: Binance 原始 API 返回 `income`（不是 `amount`）和 `incomeType`（不是 `type`）。  
> 如果直接透传，前端 `item.amount` 拿到 `undefined`，渲染为 `0.0000`，`item.type` 也为空。  
> **必须在客户端层完成字段名映射。**

### 2.8 字段映射速查表（各交易所原始 → 统一）

| 统一字段 | Binance 原始 | OKX 原始 | 说明 |
|----------|------------|----------|------|
| `symbol` | `symbol` (BTCUSDT) | `instId` (BTC-USDT-SWAP) | OKX 需要转换 |
| `quantity` | `positionAmt` | `pos` × `ctVal` | OKX 是张数 |
| `entry_price` | `entryPrice` | `avgPx` | |
| `mark_price` | `markPrice` | `markPx` | |
| `unrealized_pnl` | `unRealizedProfit` | `upl` | |
| `leverage` | `leverage` (str→int) | `lever` (str→int) | |
| `liquidation_price` | `liquidationPrice` | `liqPx` | OKX 可能为空 |
| `origQty`(订单) | `origQty` (str) | `sz` × `ctVal` (float) | |
| `side` | `side` (已大写) | `side` (需 .upper()) | |
| `income → amount` | `income` (str) | `balChg` / `pnl` / `fee` | 最大差异 |
| `incomeType → type` | `incomeType` | 由 `type` 字段推断 | OKX type="2"→交易 |
| `commission` | `commission` (str) | `fee` (str→float) | |
| `realizedPnl` | `realizedPnl` (str) | `pnl` (str→float) | |
| `time` | `time` (int, ms) | `ts` / `cTime` (str→int) | OKX 是字符串! |

---

## 3. 已知坑点清单（血泪经验）

### 3.1 类型不一致
- **Binance** 的数值字段基本都是**字符串**（`"0.002"`, `"80000.1"`）
- **OKX** 的数值字段也是字符串，但时间戳也是字符串
- **解决方案**: 在客户端层统一转为 `float` / `int`

### 3.2 数量单位差异
- **Binance**: 使用 base coin 数量（如 `0.002 BTC`）
- **OKX**: 使用合约张数（如 `2 张`），需要乘以 `ctVal`（BTC 合约面值 = 0.01）
- **解决方案**: 在 OKX 客户端缓存合约信息，每次转换

### 3.3 全仓平仓的数量为零
- **Binance**: `STOP_MARKET` / `TAKE_PROFIT_MARKET` 当 `closePosition=true` 时，`origQty="0"`
- **OKX**: 类似，`sz="0"` 且 `closeFraction="1"`
- **解决方案**: Router 层从本地 `positions` 表反查真实持仓量并回填

### 3.4 Symbol 格式
- **Binance**: `BTCUSDT`（无分隔符）
- **OKX**: `BTC-USDT-SWAP`（有分隔符和产品后缀）
- **Bybit** (参考): `BTCUSDT`（与 Binance 一致）
- **Gate.io** (参考): `BTC_USDT`（下划线分隔）
- **解决方案**: 客户端内部实现 `_convert_symbol()` 和 `_convert_symbol_back()`

### 3.5 时间戳格式
- **Binance**: 毫秒时间戳（`int`）
- **OKX**: 毫秒时间戳（`str`，需要 `int()` 转换）
- **解决方案**: 统一返回 `int` 类型的毫秒时间戳

### 3.6 订单状态映射
| 统一状态 | Binance | OKX |
|---------|---------|-----|
| `NEW` | `NEW` | `live` |
| `PARTIALLY_FILLED` | `PARTIALLY_FILLED` | `partially_filled` |
| `FILLED` | `FILLED` | `filled` |
| `CANCELED` | `CANCELED` | `canceled` |
| `EXPIRED` | `EXPIRED` | `expired` |
| `NEW` (algo) | `NEW` | `live` → 映射 |
| `WORKING` (algo) | — | `WORKING` → 映射为 `NEW` |

### 3.7 资金流水类型映射
| 统一类型 | Binance `incomeType` | OKX `type` 数字 |
|---------|---------------------|-----------------|
| `REALIZED_PNL` | `REALIZED_PNL` | `2` (pnl 部分) |
| `COMMISSION` | `COMMISSION` | `2` (fee 部分) |
| `FUNDING_FEE` | `FUNDING_FEE` | `8`, `173` |
| `TRANSFER` | `TRANSFER` | `1` |
| `DELIVERED_SETTELMENT` | `DELIVERED_SETTELMENT` | `3` |
| `INSURANCE_CLEAR` | `INSURANCE_CLEAR` | `5` |

> ⚠️ OKX 的 `type="2"`（交易）一条记录同时包含 `fee` 和 `pnl`，需要拆分为两条。

### 3.8 持仓模式
- **Binance**: `dualSidePosition: true/false`（单向/双向）
- **OKX**: `posMode: "net_mode" | "long_short_mode"`
- **解决方案**: 统一返回 `{"dualSidePosition": bool}`

---

## 4. 接入新交易所：逐步清单

### Step 1: 创建客户端文件

```
back/exchange_<name>.py
```

继承 `ExchangeClient` 基类：

```python
from exchange_base import ExchangeClient

class <Name>FuturesClient(ExchangeClient):
    def __init__(self, api_key, api_secret, ...):
        ...
    
    def get_exchange_name(self) -> str:
        return "<Name>"
```

### Step 2: 实现核心抽象方法

按以下优先级实现，每实现一个就跑一次单元测试：

| 优先级 | 方法 | 必须 | 说明 |
|--------|------|------|------|
| P0 | `test_connection()` | ✅ | 连接测试 |
| P0 | `get_usdt_balance()` | ✅ | 余额查询 |
| P0 | `get_positions()` | ✅ | 持仓查询 |
| P0 | `place_market_order()` | ✅ | 市价下单 |
| P0 | `get_mark_price()` | ✅ | 标记价格 |
| P1 | `place_stop_market_order()` | ✅ | 止损市价单 |
| P1 | `place_take_profit_market_order()` | ✅ | 止盈市价单 |
| P1 | `set_leverage()` | ✅ | 设置杠杆 |
| P1 | `set_margin_type()` | ✅ | 设置保证金模式 |
| P1 | `cancel_all_orders()` | ✅ | 取消普通挂单 |
| P1 | `cancel_all_algo_orders()` | ✅ | 取消条件单 |
| P1 | `cancel_all_orders_and_algo()` | ✅ | 取消全部 |
| P1 | `get_open_orders()` | ✅ | 查询普通挂单 |
| P1 | `get_open_algo_orders()` | ✅ | 查询条件单 |
| P1 | `get_position_mode()` | ✅ | 持仓模式 |
| P2 | `get_trade_history()` | ✅ | 成交历史 |
| P2 | `get_order_history()` | ✅ | 订单历史 |
| P2 | `get_income_history()` | ✅ | 资金流水 |
| P2 | `place_batch_orders()` | 推荐 | 批量下单 |
| P3 | `get_funding_rate()` | 可选 | 资金费率 |
| P3 | `get_leverage_bracket()` | 可选 | 杠杆档位 |
| P3 | `get_adl_quantile()` | 可选 | ADL 风险 |
| P3 | `get_force_orders()` | 可选 | 强平历史 |
| P3 | `get_commission_rate()` | 可选 | 费率查询 |

### Step 3: Symbol 转换

**必须实现** 的两个内部方法：

```python
def _convert_symbol(self, symbol: str) -> str:
    """将统一格式 BTCUSDT 转为交易所原始格式"""
    # 例如 OKX: BTCUSDT → BTC-USDT-SWAP
    # 例如 Gate: BTCUSDT → BTC_USDT
    pass

def _convert_symbol_back(self, raw_symbol: str) -> str:
    """将交易所原始格式转为统一格式 BTCUSDT"""
    pass
```

### Step 4: 注册到工厂

编辑 `exchange_factory.py`：

```python
from exchange_<name> import <Name>FuturesClient

def create_exchange_client(provider, api_key, api_secret, ...):
    ...
    elif provider == "<name>":
        return <Name>FuturesClient(
            api_key=api_key,
            api_secret=api_secret,
            ...
        )
```

### Step 5: 前端适配

编辑 `agno-chat-ui/src/components/ConnectExchangeModal.jsx`：

```javascript
// 在交易所选项列表中添加
const EXCHANGES = [
    { id: 'binance', name: 'Binance', logo: '...' },
    { id: 'okx', name: 'OKX', logo: '...' },
    { id: '<name>', name: '<Name>', logo: '...' },  // 新增
];
```

如果新交易所需要额外参数（如 OKX 的 passphrase），在表单中添加对应字段。

### Step 6: 编写验证测试

```python
# back/test_<name>.py
from exchange_<name> import <Name>FuturesClient

client = <Name>FuturesClient(
    api_key="YOUR_KEY",
    api_secret="YOUR_SECRET"
)

# 1. 连接测试
print("Connection:", client.test_connection())

# 2. 余额测试 → 确认字段名正确
balance = client.get_usdt_balance()
assert "wallet_balance" in balance, f"Missing wallet_balance! Got: {balance.keys()}"
assert isinstance(balance["wallet_balance"], float), "wallet_balance must be float"

# 3. 持仓测试 → 确认字段名和类型
positions = client.get_positions()
for p in positions:
    assert "symbol" in p and "USDT" in p["symbol"], f"Symbol format wrong: {p['symbol']}"
    assert isinstance(p["quantity"], float), "quantity must be float"
    assert isinstance(p["leverage"], int), "leverage must be int"

# 4. 资金流水测试 → 确认是 amount 不是 income
records = client.get_income_history()
for r in records:
    assert "amount" in r, f"Missing 'amount'! Got keys: {r.keys()}"
    assert "type" in r, f"Missing 'type'! Got keys: {r.keys()}"
    assert isinstance(r["amount"], float), "amount must be float"
    assert isinstance(r["time"], int), "time must be int"

print("All field validations passed!")
```

### Step 7: Router 层检查

确认 `strategy.py` 中以下端点对新交易所**不需要特殊分支**：

- ✅ `/wallet` — 使用 `get_usdt_balance()` + `get_positions()`，字段已统一
- ✅ `/positions` — 中间层 `_format_binance_positions` 依赖 `quantity`/`entry_price`/`direction` 等统一字段
- ⚠️ `/orders` — 有大量 `order.get("origQty")` 的条件单逻辑，需确认新交易所的字段一致性
- ✅ `/trade-history` — 直接读取客户端层标准化后的 `qty`/`price`/`commission` 字段
- ✅ `/position-history` — 使用 `trade.get("qty")`，已兼容
- ✅ `/income-history` — 直接透传客户端返回值，前端读 `amount`/`type`

---

## 5. 开发检查单（Checklist）

新交易所接入 PR 前，逐条确认：

- [ ] **客户端层**：所有数值字段返回 `float`/`int`，不返回字符串
- [ ] **客户端层**：`symbol` 统一为 `XXUSDT` 格式（无分隔符、无产品后缀）
- [ ] **客户端层**：`time` 统一为毫秒级 `int` 时间戳
- [ ] **客户端层**：`side` 统一为 `"BUY"` / `"SELL"` 大写
- [ ] **客户端层**：`status` 统一为 `"NEW"` / `"FILLED"` / `"CANCELED"` 大写
- [ ] **客户端层**：`get_income_history()` 返回 `amount`（不是 `income`）和 `type`（不是 `incomeType`）
- [ ] **客户端层**：`get_positions()` 返回 `quantity` 为正数，`direction` 表示方向
- [ ] **客户端层**：合约张数已转换为 base coin 数量
- [ ] **工厂注册**：`exchange_factory.py` 中添加了新的 `elif` 分支
- [ ] **前端适配**：`ConnectExchangeModal.jsx` 中添加了选项和 logo
- [ ] **验证测试**：`test_<name>.py` 全部通过
- [ ] **Router 兼容**：`/orders` 端点能正确解析新交易所的条件单

---

## 6. 附录：技术债务清理记录

### 6.1 ~~Binance 客户端大量直接透传~~ ✅ 已修复
- `get_trade_history()` → 已在客户端层格式化，所有数值统一为 `float`
- `get_open_orders()` → 已在客户端层格式化，含 `reduceOnly: bool` 等类型统一
- `get_open_algo_orders()` → 已在客户端层格式化，含 `algoId → orderId` 映射
- `get_order_history()` → 已在客户端层格式化
- `get_income_history()` → 已在客户端层完成 `income→amount`, `incomeType→type` 映射

### 6.2 ~~exchange_base.py 缺少方法声明~~ ✅ 已修复
- `get_income_history()` → 已加入 `@abstractmethod`
- `place_batch_orders()` → 已加入 `@abstractmethod`
- `get_funding_rate()` → 已加入默认实现（返回 `[]`）
- `get_leverage_bracket()` → 已加入默认实现
- `get_adl_quantile()` → 已加入默认实现
- `get_force_orders()` → 已加入默认实现
- `get_commission_rate()` → 已加入默认实现

### 6.3 strategy.py 路由层 `/orders` 端点仍较臃肿（低优先级）
`/orders` 端点单函数约 160 行，承担了：
1. 交易所 API 调用
2. 订单类型推断（条件单方向）
3. 数量智能补偿（从持仓反查）
4. 本地 DB Fallback

**建议**: 后续可抽取为 `OrderNormalizer` 类，与路由层解耦。
