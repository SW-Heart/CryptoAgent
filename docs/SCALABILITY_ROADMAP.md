# Strategy Nexus 扩展性改造路线图

> **创建日期**: 2026-04-06  
> **当前状态**: 单用户可用，5+ 用户将出现性能瓶颈  
> **优先级**: 用户增长到 5-10 人时启动改造

---

## 一、当前架构瓶颈分析

### 1. 🔴 调度器串行执行（P0 - 最致命）

**位置**: `back/scheduler.py` → `trigger_strategy()`

**问题**: 所有 trader instance 在一个 for 循环中串行执行。每次 Agent 运行需要 30-120 秒（LLM API 调用 + 数据采集 + 分析）。

```python
# 当前代码 (scheduler.py ~L534)
for idx, trader in enumerate(active_traders):
    _run_trader_instance(trader, round_id)  # 同步 HTTP 调用，阻塞等待
```

**影响**:
- 10 个用户 × 60 秒/次 = 每轮需 10 分钟
- 如果所有用户都设 60 分钟间隔，调度器每轮最多处理 60 个用户
- 超过此阈值，任务会永久堆积

---

### 2. 🔴 单进程架构（P0）

**问题**: Scheduler、FastAPI Server、Agent 执行全在同一个 Python 进程中。

- Scheduler 运行在后台线程，但 Agent 执行通过 HTTP POST 回调到本地 FastAPI
- `asyncio.to_thread` 虽然不阻塞事件循环，但线程池默认大小有限
- 单进程无法利用多核 CPU

---

### 3. 🟡 数据库连接池不足（P1）

**位置**: `back/app/database.py`

```python
pool = min=5, max=50
```

**问题**: 每个 Agent 运行期间，工具链会多次查库（余额、持仓、写日志等）。50 个并发 Agent 会耗尽连接池。

---

### 4. 🟡 外部 API 限流（P1）

| API | 限制 | 风险 |
|-----|------|------|
| Binance REST | 1200 req/min per IP | 多用户共享 IP，数据采集密集 |
| Binance Futures | 签名请求更严格 | 每用户独立限流，但服务端转发共享 IP |
| LLM API (DeepSeek/OpenAI) | RPM / TPM 限制 | 并发 Agent 同时请求会触发限流 |
| CoinGecko | 10-30 req/min (免费) | 宏观数据采集可能被封 |

---

### 5. 🟡 API Key 双系统未统一（P1）

**位置**: 
- 旧系统: `user_binance_keys` 表 → `binance_client.py`
- 新系统: `exchange_accounts` 表 → `workspace_service.py`

**问题**: 当前通过 `_get_binance_client_fallback()` 临时打通，但应统一为一套。Agent 工具链（`binance_trading_tools.py`）中的 `has_user_api_keys` / `get_user_binance_client` 仍然只查旧表。

---

### 6. 🟢 前端轮询压力（P2）

**位置**: `agno-chat-ui/src/pages/ExecutionPage.jsx`

**问题**: 每个在线用户的前端都在定时轮询 `/wallet`、`/positions`、`/logs` 等接口。用户多了会放大 API 和数据库压力。

---

## 二、改造方案

### Phase 1: 任务队列化（用户 5-10 人时）

**目标**: 将 Agent 执行从串行改为并行异步任务。

#### 技术选型
- **Celery** + **Redis** (推荐) 
- 或 **Dramatiq** + **Redis** (更轻量)

#### 改造内容

```
[Scheduler]                    [Redis Queue]              [Celery Workers x N]
trigger_strategy() ──push──►  task: run_agent(user_id) ──pull──►  Agent.run()
                              task: run_agent(user_id)            Agent.run()
                              task: run_agent(user_id)            Agent.run()
```

1. **`scheduler.py`**: `_run_trader_instance` 改为 `celery_app.send_task()` 投递任务
2. **新增 `worker.py`**: Celery Worker，接收任务并执行 Agent
3. **新增 `celery_config.py`**: 配置 broker (Redis)、并发数、任务超时等
4. **`docker-compose.yml`**: 添加 Redis 和 Worker 服务

#### 预期效果
- 支持 50-100 个用户并行
- Worker 可水平扩展（加机器 = 加处理能力）
- 任务有重试、超时、死信队列等保障

---

### Phase 2: 数据层优化（用户 10-50 人时）

#### 2.1 统一 API Key 存储
- 废弃 `user_binance_keys` 表
- 所有工具链都从 `exchange_accounts` 表读取凭证
- `binance_trading_tools.py` 中的 `_get_effective_user_id` / `has_user_api_keys` / `get_user_binance_client` 全部改用新表

#### 2.2 数据库连接池升级
```python
# 当前
pool = min=5, max=50

# 改造后
pool = min=10, max=200
# 或使用 PgBouncer 连接池代理
```

#### 2.3 缓存层
- 引入 **Redis 缓存** 热点数据：
  - 市场价格（TTL 5s）
  - 宏观数据 FnG/BTC Dominance（TTL 5min）
  - 资金费率（TTL 1min）
- 减少重复的 Binance API 调用（多用户查同一币种价格）

#### 2.4 strategy_logs 表优化
```sql
-- 添加索引
CREATE INDEX idx_strategy_logs_timestamp ON strategy_logs(timestamp DESC);
CREATE INDEX idx_strategy_logs_user ON strategy_logs(user_id, timestamp DESC);

-- 添加 user_id 列（当前缺失，所有用户混在一起）
ALTER TABLE strategy_logs ADD COLUMN user_id TEXT;
```

---

### Phase 3: 实时通信（用户 20+ 时）

#### 3.1 WebSocket 替代轮询
- 前端改用 WebSocket 连接
- 后端在 Agent 完成/持仓变化/余额变化时主动推送
- 消除无效轮询请求

```python
# FastAPI WebSocket
@app.websocket("/ws/{user_id}")
async def ws_endpoint(websocket, user_id):
    await manager.connect(websocket, user_id)
    # 推送更新...
```

#### 3.2 SSE (Server-Sent Events) 备选
- 比 WebSocket 简单，单向推送场景够用
- 前端用 `EventSource` API 即可

---

### Phase 4: 微服务化（用户 100+ 时）

将单体拆分为独立服务:

```
┌─────────────┐  ┌──────────────┐  ┌──────────────┐
│  API Gateway │  │  Agent Worker │  │  Data Service │
│  (FastAPI)   │  │  (Celery x N) │  │  (市场数据)   │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                  │
       └────────── Redis / Kafka ──────────┘
                         │
                   ┌─────┴─────┐
                   │ PostgreSQL │
                   └───────────┘
```

- **API Gateway**: 只处理 HTTP 请求、认证、路由
- **Agent Worker**: 独立部署，专门运行 LLM Agent
- **Data Service**: 统一管理市场数据获取和缓存，避免重复请求
- **消息总线**: Redis Pub/Sub 或 Kafka，用于服务间通信

---

## 三、当前已完成的优化

- [x] `asyncio.to_thread`: Agent 执行不再阻塞 FastAPI 事件循环 (`main.py`)
- [x] `_get_binance_client_fallback`: 双路径获取 API 凭证 (`strategy_context.py`)
- [x] `strategy_logs.timestamp`: 修复日志时间戳缺失问题
- [x] 重试机制: `BinanceFuturesClient._request` 内置 SSL/连接错误重试

---

## 四、监控告警（所有阶段都需要）

建议尽早引入基础监控：

```python
# 关键指标
- Agent 执行耗时（P50/P95/P99）
- 调度延迟（预定时间 vs 实际执行时间）
- DB 连接池使用率
- Binance API 剩余限流额度
- LLM API 调用成功率/延迟
- 策略日志写入成功率
```

工具选择：
- **轻量**: Prometheus + Grafana
- **简单**: 自建 `/metrics` 端点 + 定时检查脚本
- **SaaS**: Datadog / Sentry

---

## 五、容量估算参考

| 用户数 | 架构阶段 | 预计基础设施 |
|--------|---------|------------|
| 1-5 | 当前架构 | 单机 (4C8G) |
| 5-20 | Phase 1 (队列化) | 单机 + Redis |
| 20-100 | Phase 2+3 | 2-3 台服务器 + Redis + PgBouncer |
| 100+ | Phase 4 (微服务) | K8s 集群 / 云原生 |
