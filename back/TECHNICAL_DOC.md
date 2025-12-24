# Alpha Crypto Agent - 技术文档

## 项目概述

**Alpha** 是一个基于 Agno 框架构建的加密货币分析 AI Agent，具备实时市场数据获取、技术分析、新闻情报扫描等多维度分析能力。

### 核心定位
- **多维共振分析师**：结合技术面、叙事面、情绪面进行综合判断
- **多语言支持**：根据用户语言自动切换中英文回复
- **专业级工具链**：12 个自定义工具覆盖完整分析场景

### 技术栈
| 组件 | 技术 |
|------|------|
| Agent 框架 | [Agno](https://github.com/agno-ai/agno) |
| LLM | OpenAI GPT-4 |
| 后端 | Python + FastAPI |
| 前端 | React + Vite |
| 数据库 | SQLite (会话历史) |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React)                        │
│                   agno-chat-ui/src/App.jsx                   │
└─────────────────────────────────┬───────────────────────────┘
                                  │ WebSocket / REST
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                      Backend (Python)                        │
│                     back/api_start.py                        │
└─────────────────────────────────┬───────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                     Agno Agent                               │
│                   back/crypto_agent.py                       │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ System Prompt (instructions)                            ││
│  │ - Identity & Personality                                ││
│  │ - Toolbox Description                                   ││
│  │ - Analysis Frameworks (RSI, Fear/Greed, etc.)           ││
│  │ - Operating Modes (Sniper, Analyst, Researcher...)      ││
│  │ - Output Guidelines & Guardrails                        ││
│  └─────────────────────────────────────────────────────────┘│
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Tools (back/crypto_tools.py)                            ││
│  │ - Market Data Tools (7)                                 ││
│  │ - Search Tools (4)                                      ││
│  │ - Third-party Tools (DuckDuckGo, Exa)                   ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────┬───────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                    External APIs                             │
│  Binance | DexScreener | CoinGecko | CryptoPanic | Serper   │
└─────────────────────────────────────────────────────────────┘
```

---

## 文件结构

```
zidingyi/
├── back/
│   ├── crypto_agent.py      # Agent 定义 & 系统提示词
│   ├── crypto_tools.py      # 自定义工具函数
│   ├── api_start.py         # FastAPI 后端入口
│   └── .env                  # 环境变量 (API Keys)
│
├── agno-chat-ui/
│   ├── src/
│   │   └── App.jsx          # 前端主组件
│   └── package.json
│
└── tmp/
    └── test.db              # SQLite 会话历史数据库
```

---

## 环境变量配置

在 `back/.env` 中需要配置以下 API Keys：

```bash
OPENAI_API_KEY=sk-xxx           # OpenAI API Key (必需)
SERPER_API_KEY=xxx              # Google Search API (推荐)
CRYPTOPANIC_API_KEY=xxx         # CryptoPanic 新闻 API (推荐)
EXA_API_KEY=xxx                 # Exa 深度搜索 API (可选)
```

---

## 工具详细文档

### 1. 市场数据工具 (Market Data Tools)

#### 1.1 `get_token_analysis(symbol: str)`

**功能**：获取指定代币的实时价格和技术分析

**数据源**：
1. **Binance API** (优先) - 主流代币，提供 K 线数据用于技术指标计算
2. **DexScreener API** (备用) - Meme 币和 DEX 代币

**技术指标**：
- RSI (14 周期)
- EMA20 / EMA50
- 趋势判断 (Strong Uptrend / Downtrend / Pullback / Sideways)
- 支撑位估算

**产品使用场景**：
| 用户问题示例 | 触发条件 |
|--------------|----------|
| "BTC 现在多少钱？" | 询问价格 |
| "ETH 能买吗？" | 买卖决策 |
| "SOL 的技术面怎么样？" | 技术分析 |
| "PEPE 超买了吗？" | RSI 判断 |

**返回示例**：
```
[BTC Analysis]
Data Source: Binance (CEX)
Price: $97,234.5600
Trend: Strong Uptrend
RSI: 62.3 - Neutral
Support (EMA20): $94,521.3400
```

**注意事项**：
- Binance API 在中国大陆需要 VPN
- 对于链上 Meme 币，不提供 RSI 指标（DexScreener 无 K 线）

---

#### 1.2 `get_market_sentiment()`

**功能**：获取市场贪婪/恐惧指数

**数据源**：Alternative.me Fear & Greed Index API

**指数解读**：
| 区间 | 状态 | 含义 |
|------|------|------|
| 0-20 | Extreme Fear | 市场极度恐慌，可能是抄底机会 |
| 20-40 | Fear | 市场悲观 |
| 40-60 | Neutral | 方向不明 |
| 60-80 | Greed | 市场贪婪，注意风险 |
| 80-100 | Extreme Greed | 极度贪婪，可能见顶 |

**产品使用场景**：
| 用户问题示例 | 触发条件 |
|--------------|----------|
| "市场情绪怎么样？" | 情绪查询 |
| "大盘恐慌吗？" | 恐慌判断 |
| "现在适合抄底吗？" | 情绪参考 |

**返回示例**：
```
Fear & Greed Index: 72 - Status: Greed
```

---

#### 1.3 `get_market_hotspots()`

**功能**：获取当前热搜代币 Top 5

**数据源**：CoinGecko Trending API

**产品使用场景**：
| 用户问题示例 | 触发条件 |
|--------------|----------|
| "什么币最火？" | 热度查询 |
| "大家都在搜什么？" | 趋势发现 |
| "有什么热门代币？" | 机会发现 |

**返回示例**：
```
Trending coins: PEPE, WIF, BONK, RENDER, TAO
```

---

#### 1.4 `get_btc_dominance()`

**功能**：获取 BTC 市值占比和山寨季指标

**数据源**：CoinGecko Global API

**市场阶段判断**：
| BTC 占比 | 阶段 | 山寨币策略 |
|----------|------|------------|
| > 60% | BTC Draining | 减少山寨仓位 |
| 55-60% | BTC Dominant | 只配置强势山寨 |
| 50-55% | Balanced | 适度配置 |
| 40-50% | Alt Active | 积极布局 |
| < 40% | Alt Season | 全力山寨 |

**产品使用场景**：
| 用户问题示例 | 触发条件 |
|--------------|----------|
| "现在是山寨季吗？" | 山寨季判断 |
| "BTC 吸血严重吗？" | 资金流向 |
| "应该买山寨还是大饼？" | 配置建议 |

**返回示例**：
```
BTC Dominance: 54.3%
ETH Share: 12.1%
Total Market Cap: $3.42T
Market Phase: Balanced - BTC and alts share the market
```

---

#### 1.5 `get_funding_rate(symbol: str = "BTC")`

**功能**：获取永续合约资金费率

**数据源**：Binance Futures API

**费率解读**：
| 费率 | 含义 | 风险 |
|------|------|------|
| > 0.1% | 极度看多 | 多头拥挤，可能多杀多 |
| 0.05-0.1% | 偏多 | 多头主导 |
| 0-0.05% | 轻微看多 | 健康 |
| -0.05-0% | 轻微看空 | 健康 |
| < -0.1% | 极度看空 | 空头拥挤，可能空头回补 |

**产品使用场景**：
| 用户问题示例 | 触发条件 |
|--------------|----------|
| "BTC 资金费率多少？" | 费率查询 |
| "合约多空比怎么样？" | 杠杆情绪 |
| "会不会爆仓？" | 风险判断 |

**返回示例**：
```
BTC Funding Rate: 0.0234%
Interpretation: Slightly Bullish - Healthy state
```

---

#### 1.6 `get_pro_crypto_news(filter_type: str = "hot")`

**功能**：获取加密新闻 + 社区情绪投票

**数据源**：CryptoPanic API v2

**参数**：
- `filter_type`: `"hot"` (热门) | `"rising"` (上升) | `"important"` (重要)

**产品使用场景**：
| 用户问题示例 | 触发条件 |
|--------------|----------|
| "币圈发生了什么？" | 新闻查询 |
| "有什么利好利空？" | 情绪判断 |
| "最近有什么大新闻？" | 事件追踪 |

**返回示例**：
```
[Crypto News Radar (HOT)]
- [coindesk.com] Bitcoin Surges Past $100K
  Sentiment: Bullish (42 votes) [HOT]
- [decrypt.co] Ethereum ETF Inflows Hit Record
  Sentiment: Bullish (18 votes)
```

---

#### 1.7 `get_narrative_dominance()`

**功能**：分析当前主导叙事/赛道热度

**数据源**：CryptoPanic + 关键词分析

**分析赛道**：AI、Meme、RWA、Layer2、Solana、Regulation、Macro、DeFi

**产品使用场景**：
| 用户问题示例 | 触发条件 |
|--------------|----------|
| "哪个赛道最火？" | 板块热度 |
| "AI 币还热吗？" | 叙事判断 |
| "资金在往哪流？" | 板块轮动 |

**返回示例**：
```
[Current Market Narrative Strength]
AI: ████████ (8)
Meme: █████ (5)
Regulation: ███ (3)
```

---

### 2. 搜索工具 (Search Tools)

#### 2.1 `search_news(query: str, num_results: int = 5)`

**功能**：Google News 新闻搜索

**数据源**：Serper API (Google News)

**产品使用场景**：
| 用户问题示例 | 触发条件 |
|--------------|----------|
| "特朗普加密货币新闻" | 话题搜索 |
| "ETH ETF 最新消息" | 事件跟踪 |
| "SEC 监管动态" | 政策研究 |

**返回示例**：
```
Latest news for 'Bitcoin ETF':

1. BlackRock Bitcoin ETF Sees Record Inflows
   Date: 2 hours ago | Source: Bloomberg
   BlackRock's IBIT recorded $500M in inflows...
   Link: https://...
```

---

#### 2.2 `search_google(query: str, num_results: int = 5)`

**功能**：Google 通用搜索 + 知识图谱

**数据源**：Serper API (Google Search)

**产品使用场景**：
| 用户问题示例 | 触发条件 |
|--------------|----------|
| "Solana 是什么？" | 概念解释 |
| "RENDER 团队背景" | 项目研究 |
| "Uniswap 官网" | 资料查找 |

---

#### 2.3 `duckduckgo_search` / `duckduckgo_news`

**功能**：备用搜索工具

**来源**：Agno 内置 DuckDuckGoTools

**使用场景**：当 Serper API 额度用尽时自动切换

---

#### 2.4 `exa_search`

**功能**：深度内容搜索

**来源**：Agno 内置 ExaTools

**使用场景**：需要学术级深度研究时使用

---

## 系统提示词架构

系统提示词位于 `crypto_agent.py` 的 `instructions` 参数中，分为以下模块：

### 1. IDENTITY (身份定义)
- 角色：Alpha，资深加密分析师
- 核心理念：多维共振交易法
- 性格特点：观点鲜明、数据驱动、风险优先
- **语言规则**：根据用户语言切换中英文

### 2. TOOLBOX (工具箱)
- 工具用途映射表
- 搜索策略指导

### 3. ANALYSIS FRAMEWORKS (分析框架)
- RSI + 趋势解读矩阵
- 多维共振判断矩阵
- 市场陷阱识别 (Bull Trap / Bear Trap)
- 恐慌贪婪指数深度解读
- BTC 主导率解读
- 资金费率解读
- 新闻影响力评估

### 4. OPERATING MODES (工作模式)
| 模式 | 触发词 | 执行流程 |
|------|--------|----------|
| Sniper | buy, sell, entry | 技术分析 → 新闻验证 → 情绪检查 → 点位建议 |
| Analyst | why pump, what happened | 新闻搜索 → 恐慌指数 → 资金流向 → 事件定性 |
| Researcher | what is, whitepaper | 项目搜索 → 技术分析 → 投资价值判断 |
| Intelligence | check these, batch | 循环分析 → 对比排序 |
| Coach | explain, how to | 概念搜索 → 简单解释 |
| Quick Q&A | price of | 直接调用 → 简洁返回 |

### 5. OUTPUT GUIDELINES (输出规范)
- 结构化输出模板
- 输出原则（观点鲜明、数据支撑、风险提示）

### 6. GUARDRAILS (禁区)
- 严禁编造数据
- 必须调用工具验证
- 保护用户本金优先

---

## API 依赖说明

| API | 用途 | 是否必需 | 免费额度 |
|-----|------|----------|----------|
| Binance | 代币价格/K线 | 是 | 无限（公开API） |
| DexScreener | Meme币价格 | 是 | 无限（公开API） |
| CoinGecko | 热搜/BTC占比 | 是 | 有限（公开API） |
| Alternative.me | 恐慌指数 | 是 | 无限（公开API） |
| CryptoPanic | 新闻情报 | 推荐 | 无限（需申请Key） |
| Serper | Google搜索 | 推荐 | 2500次/月 |
| Exa | 深度搜索 | 可选 | 有限 |

---

## 本地开发指南

### 1. 环境准备

```bash
# 创建虚拟环境
cd back
python -m venv venv
source venv/bin/activate  # Mac/Linux
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install agno requests pandas pandas_ta python-dotenv
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入 API Keys
```

### 3. 启动后端

```bash
cd back
python api_start.py
# 后端运行在 http://localhost:8000
```

### 4. 启动前端

```bash
cd agno-chat-ui
npm install
npm run dev
# 前端运行在 http://localhost:5173
```

---

## 常见问题

### Q: Binance API 无法访问
**A**: 中国大陆 IP 被封锁，需要使用 VPN 或部署到海外服务器

### Q: CoinGecko API 频繁 429
**A**: 免费 API 有速率限制，可以：
1. 降低调用频率
2. 升级到 Pro API

### Q: Agent 回复语言不对
**A**: 系统提示词 IDENTITY 部分有 Language Rule，确保提示词是全英文

---

## 版本历史

| 版本 | 日期 | 主要更新 |
|------|------|----------|
| v2.0 | 2024-12-10 | 全英文系统提示词支持多语言回复 |
| v1.9 | 2024-12-10 | 新增 get_btc_dominance, get_funding_rate |
| v1.8 | 2024-12-09 | 精简工具 Docstring，消除冗余 |
| v1.7 | 2024-12-08 | 添加分析框架矩阵 |
| v1.0 | 2024-12-06 | 初始版本 |
