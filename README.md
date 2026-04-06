# 🤖 CryptoAgent: 开发者与 AI 助手工程手册 (Internal)

> **项目状态**: 生产现代化重构已完成 (Phase 2)
> **核心架构**: Agno Agentic Core + FastAPI Async + React 18 High-Fidelity UI

本手册旨在为内部开发人员及协作 AI 助手提供项目深度技术细节，以便进行高效的逻辑维护与功能扩展。

---

## 🏗️ 1. 系统架构深度解构

### 1.1 Agent 决策流 (Agno Core)
系统采用 **双层 Agent 架构**，逻辑层级如下：
*   **CryptoAnalyst (数据感知层)**:
    *   **职责**: 负责多源异步数据采集（Binance Ticker, Farside ETF Flows, CryptoPanic Sentiment）。
    *   **输出**: 格式化的市场共振综述（Market Resonance Summary）。
*   **TradingStrategy (决策执行层)**:
    *   **职责**: 接收感知层数据，结合用户配置的 `StrategyProfile`（如：Risk per Trade, Max Positions），输出结构化决策命令。
    *   **Action Set**: `start`, `stop`, `adjust_risk`, `panic_sell`。

### 1.2 多模型统一转换层
为了屏蔽不同 LLM 厂商的 Prompt 差异，系统在 `back/agents` 层级实现了统一适配：
*   支持 OpenAI (GPT-4o), Anthropic (Claude 3.5), DeepSeek-V3, Google Gemini。
*   **AI 助手注意**: 所有 Agent 的输出均强制要求 JSON 结构化，以便解析器（Parser）直接对接交易执行器。

---

## 🗄️ 2. 后端数据持久化与连接策略

### 2.1 数据库连接池 [CRITICAL]
系统已从 SQLite 迁移至 PostgreSQL，并针对高频轮询业务进行了深度优化：
*   **连接池配置**: `ThreadedConnectionPool` (Min: 5, Max: 50)。
*   **代码规范**: 严禁直接调用 `conn.close()`。必须使用 `with get_db() as conn:` 上下文管理器或 `try...finally` 块确保连接强制归还。
*   **防泄漏记录**: 2026-04-05 修复了 `binance_client.py` 辅助函数中因缺少 `try...finally` 导致的连接池枯竭问题。

### 2.2 状态同步 (Legacy Sync Mechanism)
系统目前处于过渡期，存在 `sync_legacy_workspace_state` 逻辑：
*   **原理**: 每次加载实例列表时，系统会扫描传统的 `user_binance_keys` (KV 存储)，并自动在 `exchange_accounts` (Workspace 模型) 中物化记录。
*   **物理解绑联动**: 为了防止已删除账户“复活”，`delete_exchange_account` 必须同时调用 `binance_client.delete_user_api_keys` 来销毁底层物理密钥。

---

## 💻 3. 前端工程化与 UI 架构

### 3.1 实例中心化状态管理 (Flux/Context)
前端 `ExecutionPage.jsx` 采用轮询 + 差分更新策略：
*   **状态枚举**: `PENDING`, `RUNNING`, `STOPPED`, `ERROR`。
*   **决策回显**: 决策日志通过 `/api/workspace/trader-instances/{id}/logs` 异步拉取，支持 ANSI 到 HTML 的动态转换以保证原生终端感。

### 3.2 UI 组件进阶逻辑
*   **ConfirmModal (Portal 策略)**: 
    *   **问题**: 父容器动画（`animate-in`）创建了新的堆叠上下文，导致普通 `fixed` 弹窗无法全局居中。
    *   **修复**: 使用 React `createPortal` 将所有模态框挂载至 `document.body` 最顶层，彻底解决偏移问题。
*   **Button (Variant 系统)**:
    *   避免直接透传布尔属性（如 `outline={true}`）给 DOM 元素，所有风格均通过 `variant` 字符串标识符控制。

---

## 🛠️ 4. AI 助手维护指南 (Agent Rules)

当协作 AI 进行代码修改时，必须遵循以下 **“铁律”**：

1.  **DB 读写自闭环**: 任何涉及数据库的函数，起始位置必须是 `conn = get_db_connection()`，且必须配套 `finally: conn.close()`。
2.  **API 响应一致性**: 所有接口必须返回 `{"success": true, ...}` 或标准的错误 JSON。
3.  **UI 动效连贯性**: 修改 SettingsPage 等面板时，注意保留 Framer Motion 的 `animate-in` 类名。
4.  **影子删除禁止**: 在 `workspace_service.py` 修改删除逻辑时，务必检查是否在文件末尾存在重复定义（Python 的后向覆盖特性）。

---

## 📊 5. 部署参考 (Env Config)

| 变量名 | 必填 | 内部开发建议 |
| :--- | :--- | :--- |
| `DB_URL` | 是 | 生产环境建议配套 PgBouncer。 |
| `ENCRYPTION_KEY` | 是 | 用于加密物理 API Key，严禁在日志中打印。 |
| `DEEPSEEK_API_KEY` | 否 | 建议作为默认决策模型。 |
| `SUPABASE_KEY` | 是 | 负责前端 Auth，不可与后端 DB Token 混淆。 |

---
**版本控制**: v2.1.0-modernized
**最后更新**: 2026-04-05
**维护者**: Antigravity AI Engine
