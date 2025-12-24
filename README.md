# Crypto AI Agent

一个基于 AI 的加密货币分析和交易助手，集成了实时市场数据、技术分析、新闻情报等功能。

## 项目结构

```
zidingyi/
├── agno-chat-ui/          # 前端 (React + Vite)
│   ├── src/
│   │   ├── components/    # React 组件
│   │   ├── services/      # API 服务
│   │   ├── utils/         # 工具函数
│   │   └── locales/       # 国际化文件
│   └── ...
│
├── back/                  # 后端 (Python + FastAPI)
│   ├── main.py           # 入口文件
│   ├── crypto_agent.py   # AI Agent 核心
│   ├── crypto_tools.py   # 加密货币工具集
│   ├── trading_tools.py  # 交易相关工具
│   ├── technical_analysis.py  # 技术分析
│   ├── pattern_recognition.py # 形态识别
│   └── ...
│
└── README.md
```

## 功能特性

- 🤖 **AI 智能对话** - 基于 DeepSeek 的加密货币专家
- 📊 **实时行情** - 价格、成交量、市值等数据
- 📈 **技术分析** - K线形态、指标计算、趋势分析
- 📰 **新闻情报** - 实时加密货币新闻和情绪分析
- 💱 **模拟交易** - 虚拟交易功能
- 📧 **日报订阅** - 每日市场分析报告

## 快速开始

### 环境要求

- Node.js >= 18
- Python >= 3.10
- pnpm / npm

### 后端配置

```bash
cd back

# 复制环境变量模板
cp .env.example .env

# 编辑 .env 填入你的 API 密钥
# 需要配置: DeepSeek、Serper、Exa 等 API Key

# 安装依赖
pip install -r requirements.txt

# 启动后端
python main.py
```

### 前端配置

```bash
cd agno-chat-ui

# 复制环境变量模板
cp .env.example .env

# 编辑 .env 填入 Supabase 配置

# 安装依赖
pnpm install

# 启动开发服务器
pnpm dev
```

## API 密钥获取

| 服务 | 用途 | 获取地址 |
|------|------|----------|
| DeepSeek | AI 模型 | https://platform.deepseek.com/ |
| Serper | Google 搜索 | https://serper.dev/ |
| Exa | 新闻搜索 | https://exa.ai/ |
| CryptoPanic | 加密新闻 | https://cryptopanic.com/developers/api/ |
| Etherscan | 链上数据 | https://etherscan.io/myapikey |
| Supabase | 用户认证 | https://supabase.com/ |

## 技术栈

**前端**
- React 18 + Vite
- TailwindCSS
- i18next (国际化)
- Supabase Auth

**后端**
- FastAPI
- Agno (AI Agent 框架)
- DeepSeek API

## License

MIT
