# 🤖 CryptoAgent: 开发者与 AI 助手工程手册 (Internal)

> **项目状态**: 生产现代化重构已完成 (Phase 4)
> **核心架构**: Agno Agentic Core + FastAPI Async + React 18 High-Fidelity UI + Dockerized Deployment

本手册旨在为内部开发人员及协作 AI 助手提供项目深度技术细节，以便进行高效的逻辑维护与功能扩展。

---

## 🏗️ 1. 系统架构深度解构

### 1.1 Agent 决策流 (Agno Core)
系统采用 **双层 Agent 架构**，逻辑层级如下：
*   **CryptoAnalyst (数据感知层)**:
    *   **职责**: 负责多源异步数据采集，现已完全拆分到 `tools/market/` 模块下（包含 `composite.py`, `data_sources.py`, `onchain.py`, `news.py` 等）。
    *   **输出**: 格式化的市场共振综述（Market Resonance Summary）。
*   **TradingStrategy (决策执行层)**:
    *   **职责**: 接收感知层数据，结合用户配置的 `StrategyProfile`（单笔风控、杠杆策略），通过 `scheduler.py` 调度执行结构化决策。
    *   **防重复锁**: 使用单实例运行锁 (`_running_trader_instances`) 及乐观锁 (`last_analyzed_at`) 确保多线程并发不导致重复开仓。

### 1.2 多交易所抽象层 (Multi-Exchange Factory)
已完成跨交易所的底层适配，消除对单一 Binance 实例的强依赖：
*   **核心模块**: `server/exchanges/factory.py` 提供工厂模式路由。
*   **支持平台**: 现不仅支持 Binance，还拓展至 OKX、Bitget，统一了 `open_position`, `close_position`, `cancel_algo_order` 等抽象接口。
*   **模块化解耦**: 传统的 `exchange_trading_tools.py` 已降级为向下兼容层，核心逻辑彻底按业务领域拆分至 `tools/trading/` (如 `positions`, `orders`, `risk`, `cleanup`)。

---

## 🗄️ 2. 后端数据持久化与高并发优化

### 2.1 数据库连接池 [CRITICAL]
基于 PostgreSQL 的高频轮询业务优化配置：
*   **代码规范**: 严禁直接调用 `conn.close()`。必须使用 `with get_db() as conn:` 或 `try...finally` 块确保连接强制归还。

### 2.2 性能与安全优化 (Performance & Security)
*   **Workspace TTL 缓存**: 在 `workspace_service.py` 的 `sync_legacy_workspace_state` 引入基于 user_id 的 60s 内存缓存，彻底消除了由高频数据库全表轮询和 Upsert 引发的 UI 查询 3秒 延迟。
*   **加密密钥单例化**: 修复了之前按需初始化 `Fernet` 导致每次加解密都执行 100,000 次 `PBKDF2` 哈希计算造成的严重 CPU 阻塞，改为模块级缓存机制。

---

## 💻 3. 前端工程化与 UI 架构

### 3.1 组件原子化
Web 端的 Execution 页面已经完成了原子化重构：
*   将庞大的逻辑分拆为独立的 `DecisionCard.jsx`, `Dropdowns.jsx`, `StatCard.jsx`。
*   引入了高频轮询的数据防抖与 ANSI 到 HTML 的全彩原生终端日志解析，显著提升 Agent 日志反馈界面的高级感。

### 3.2 UI 动效系统
*   使用 Framer Motion，所有 Modal 已采用 React `createPortal` 挂载，彻底解决在复杂 `absolute` 流中的堆叠上下文问题。

---

## 🛠️ 4. AI 助手维护指南 (Agent Rules)

当协作 AI 进行代码修改时，必须遵循以下 **“铁律”**：

1.  **DB 读写自闭环**: 任何涉及数据库的函数，起始位置必须是 `conn = get_db_connection()`，且必须配套 `finally: conn.close()`。
2.  **动作追踪完整性**: 在新增或修改实盘交易工具 (`binance_open_position` 等) 时，必须保证在交易成功后调用 `add_session_action("ACTION_NAME")`，否则前端决策卡片将错误显示为“持仓观望”。
3.  **加密解密高昂成本**: 绝不允许在每一行查询结构里循环创建新的加解密器实例，必须重用。
4.  **按需引入与统一入口**: 新增交易所 SDK 开发，需严格遵守 `UnifiedExchangeClient` 接口，在 `exchanges/` 里完成封装，最终统一挂载至 `factory.py`。

---

## 📊 5. 容器化部署架构 (Dockerization)

当前系统已支持 `Docker Compose` 一键部署验证。
*   **路径**: 部署及编排文件位于 `deploy/` 目录。
*   **双阶段构建**: `deploy/Dockerfile` 实现了 Frontend Vite 的预编译及 Backend FastAPI 的单容器结合，通过 `nginx.conf` 暴露端口 80。
*   **命令规范**: 要求在**项目根目录**运行打包，指定路径：`docker buildx build -f deploy/Dockerfile -t xxx .`
*   **环境变量**: API 密钥统一交由 `.env` 或 Docker Compose 管理，宿主机不要留空变量以免覆盖 `.env` 配置。

---
**版本控制**: v2.2.0 (Framework Modularization)
**最后更新**: 2026-04-13 
**维护者**: Antigravity AI Engine
