# 🛠️ 智能体工具名录 (Tools & Agents Directory)

本文件详述了本项目中所有可用的工具函数、其核心功能，以及各智能体（Agent）的使用情况，供后续开发参照。

---

## 🤖 智能体概览 (Agents Overview)

| 智能体名称 (Agent Name) | 核心职责 | 工具配置重点 |
| :--- | :--- | :--- |
| **CryptoAnalyst** | 深度市场分析与咨询 | 多维度技术分析、链上数据、K线视觉 |
| **TradingStrategy** | 策略决策与实盘/模拟执行 | 执行类工具 (开平仓)、一站式分析、K线视觉 |
| **CryptoDailyReporter** | 每日早报生成 | 宏观数据、ETF流向、市场热点、新闻汇总 |
| **SuggestedQuestions** | 首页引导问题生成 | (LLM驱动) 基于日报内容生成推荐问题 |

---

## 🧰 工具模块详情 (Tool Modules)

### 1. K线视觉分析 (`kline_analysis.py`)
| 工具函数 | 功能描述 | 使用智能体 |
| :--- | :--- | :--- |
| `analyze_kline` | 生成 TradingView 趋势图 (CHART-IMG)，调用 GPT-4o-mini 进行视觉分析。 | `CryptoAnalyst`, `TradingStrategy` |

### 2. 专业技术分析 (`technical_analysis.py`)
| 工具函数 | 功能描述 | 使用智能体 |
| :--- | :--- | :--- |
| `get_multi_timeframe_analysis` | **核心入口**：提供多周期 (日线/4H) 综合趋势评价。 | 几乎所有 Agent |
| `get_vegas_channel` | Vegas 通道结构分析 (多空分水岭)。 | `TradingStrategy` |
| `get_ema_structure` | EMA 多头/空头排列结构识别。 | `TradingStrategy` |
| `get_macd_signal` | MACD 顶背离/底背离及交叉分析。 | `TradingStrategy` |
| `get_volume_analysis` | 量价共振分析，识别缩量回调或放量突破。 | `TradingStrategy` |
| `get_volume_profile` |筹码分布分析 (POC/关键位)。 | `TradingStrategy` |

### 3. 加密数据工具箱 (`crypto_tools.py`)
*此模块大多为“一站式”合并工具，旨在降低 LLM Token 消耗。*

| 工具函数 | 功能描述 | 使用智能体 |
| :--- | :--- | :--- |
| `get_macro_overview` | 合并：恐贪指数、BTC主导率、全球总市值。 | `TradingStrategy` |
| `get_batch_technical_analysis`| 批量分析多个币种的周期对齐、EMA、ATR及费率。| `TradingStrategy`, `CryptoAnalyst` |
| `get_key_levels` | 寻找 Fib、EMA、POC 的关键共振区。 | `TradingStrategy`, `CryptoAnalyst` |
| `get_pro_crypto_news` | 获取深度加密新闻，区别于通用新闻。 | 几乎所有 Agent |
| `get_trending_tokens` | 列出当前热门代币榜单。 | 几乎所有 Agent |
| `get_market_hotspots` | 识别当前市场板块热点 (Sector Rotation)。 | `DailyReporter` |

### 4. 交易执行工具 (`binance_trading_tools.py` & `trading_tools.py`)
| 工具函数 | 功能描述 | 使用智能体 |
| :--- | :--- | :--- |
| `open_position` | 在 Binance 合约开仓 (真实交易)。 | `TradingStrategy` |
| `close_position` | 平仓指令，支持部分平仓。 | `TradingStrategy` |
| `get_positions_summary` | 查询 Binance 当前权益、保证金及持仓明细。 | `TradingStrategy` |
| `set_price_alert` | 设置价格触发警报。 | `TradingStrategy`, `CryptoAnalyst` |
| `log_strategy_analysis` | 将策略分析过程记录到本地数据库。 | `TradingStrategy` |

### 5. 宏观参考工具 (`etf_tools.py`)
| 工具函数 | 功能描述 | 使用智能体 |
| :--- | :--- | :--- |
| `get_etf_daily` | 查询每日 BTC/ETH ETF 资金净流向。 | `DailyReporter`, `TradingStrategy` |

---

## 📝 开发者指南
1. **工具新增**：若新增分析类工具，请优先考虑在 `technical_analysis.py` 实现底层逻辑，然后在 `crypto_tools.py` 封装“一站式”入口以节省 Token。
2. **Agent 引用**：核心交易逻辑应始终引用 `binance_trading_tools.py` 中的函数，而非仅具模拟意义的 `trading_tools.py` 原生版本。
3. **视觉分析**：`analyze_kline` 返回的是文本分析结果。如果需要图片 URL 供前端显示，需调用内部的 `get_chart_image`。
