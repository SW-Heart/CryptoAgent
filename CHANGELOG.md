# 更新日志 / Changelog

## [2026-04-12] Phase 4 架构专业化与极致性能优化

### ⚡️ 核心性能飙升
- **消除 API 延迟**: 为 Workspace 同步引入基于 `user_id` 的 60s TTL 缓存，消除设置界面由于重复 DB 同步造成的 3+ 秒高延迟。
- **解密计算重构**: 修复 `Fernet` 实例化导致的 100,000 次 PBKDF2 重复推导 CPU 阻塞瓶颈，改为模块级全局单例。

### 🏗️ 后端深度模块化
- **交易模块解耦**: 原臃肿的 `exchange_trading_tools` 被完全解体，演变为强垂直的 `tools/trading/` (`orders.py`, `positions.py`, `risk.py`, `cleanup.py`)。
- **市场模块打散**: 将信息收集拆分为 `tools/market/` (`onchain.py`, `news.py`, `composite.py` 等)。
- **部署架构升级**: 引入 `deploy/` 目录，修复 `Dockerfile` 复制路径问题，提供 React+FastAPI 双环境结合的现代化部署方案。

### 🐛 调度器与 Agent 关键修复
- **重复触发拦截**: 修复杂乱的 `last_analyzed_at` 后置更新机制导致的 60 分钟间隔却在 3 分钟内重复触发策略的问题。
- **UI 状态回显**: 在实盘开仓/平仓统一接入 `add_session_action` 动作追踪管道，解决前端日志卡片永远显示“持仓观望”的问题，修复“正在同步中”的幽灵日志流。

---

## [2026-04-10] 多交易所适配 (Multi-Exchange Architecture)

- **抽象层映射**: 将底层客户端升级为工厂模式路由，抽象出 `UnifiedExchangeClient`。
- **全面覆盖**: 现已支持 **Binance**, **OKX**, **Bitget** 甚至 **Gate** 的统一标准挂单及资产查询流。
- **交互优化**: 优化了 Dashboard 界面的数据聚合和组件分发。

---

## [2026-04-09] 专业看盘看板集成

- **TradingView 植入**: 重磅上线专业级 Market 看板，内嵌 TradingView 无缝看盘方案。
- **交易面板加固**: 修复了 Binance 可用余额获取、历史持仓及开仓失败等系列核心资产链路 Bug。

---## [2026-01-01] Trading Agent 优化

### 🔧 工具合并优化 (Token 消耗减少 81%)

**新增合并工具:**
- `get_macro_overview()` - 合并恐贪指数 + BTC主导率 + 市值
- `get_batch_technical_analysis(symbols)` - 合并周期对齐 + EMA + ATR + 费率
- `get_key_levels(symbol)` - 合并 Fib + EMA + POC + 共振区

**效果:**
| 指标 | 优化前 | 优化后 |
|-----|-------|-------|
| Token 消耗 | 127K | 24K (-81%) |
| 工具调用次数 | 17次 | 6次 |
| 工具数量 | 20个 | 14个 |

---

### 📐 新增技术分析工具

**斐波那契工具:**
- `get_fibonacci_levels(symbol, timeframe)` - 自动识别波段高低点，计算回撤/延伸位
- `batch_fibonacci(symbols, timeframe)` - 批量斐波那契分析
- 支持周期: 15m, 1h, 4h, 1d, 1w

**共振区识别工具:**
- `find_confluence_zones(symbol)` - 多指标重叠区域检测
- 整合: ATH + EMA21/55/200 + Vegas通道 + Fib + POC + 趋势线

**增强趋势线工具:**
- 识别: 三角收敛、上升/下降三角形、通道、旗形
- 删除: 不可靠的双顶双底、头肩形态、波浪理论

---

### 📊 修复周期对齐逻辑

**修正 "顺大逆小" 原则:**
- ❌ 旧逻辑: 大小周期不一致 = "冲突" (负面信号)
- ✅ 新逻辑: 大周期多头 + 小周期回调 = **做多机会**

**两种入场策略:**
1. 回调/反弹入场 (左侧交易)
2. 突破入场 (右侧交易)

---

### 💰 完善仓位计算

**以损定仓原则:**
```
名义仓位 = 可接受亏损 / 止损距离
```

**风险限制:**
- BTC / ETH: 单笔最大亏损 ≤ 10% 账户
- 山寨币: 单笔最大亏损 ≤ 2% 账户

**TP1 止损保本规则:**
- 第一止盈触发后，止损移动到开仓价

---

### 🗑️ 删除的功能

- `detect_chart_patterns` (双顶双底/头肩形态) - 程序化识别不准确
- `analyze_wave_structure` (波浪理论) - 过于主观，难以量化
- 10个冗余的单个工具 (已被批量工具替代)

---

## [2025-12-30] Phase 2 多链扩展

- 新增 Bitcoin, TON, Tron 链余额查询
- 新增 ETF 工具集成

---

## [2025-12-29] 策略调度器控制

- 前端调度器开关控制
- 策略日志无限滚动

---
