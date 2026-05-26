# Run Events Real Streaming TODO

## 当前目标

采用方案 1：运行时流式落库，现有 SSE 端点继续从 `run_events`
轮询并输出事件。

### 后端

- 为 `AgentRuntime` 增加流式执行入口，优先基于 LangChain/LangGraph
  async stream API 产出标准化事件。
- 在 `run_agent_test` 中边消费 runtime stream，边写入 `run_events`。
- 保留 `/api/runs/{run_id}/events?after=N` 的 replay/follow 语义。
- 对 message delta 做简单合并或节流，避免每个 token 都独立提交数据库。
- 异常时保留已持久化的 partial events，并写入 terminal `error` event。

### 前端

- 扩展 run event reducer，支持 `messages.payload.delta` 追加渲染。
- 保留 `messages.payload.messages` 作为最终输出或兼容旧事件格式。
- 确保 reconnect 后继续使用 latest sequence，不清空已收到事件。

### 测试

- 本地完整联调用 Postgres 13，与目标运行环境保持一致。
- 启动后端、前端和数据库，走真实浏览器触发 SOP 质检 run。
- 覆盖 runtime stream 到 run event 的映射。
- 覆盖成功流：`custom -> messages(delta...) -> messages(final) -> done`。
- 覆盖中途异常：保留 partial events，写入 `error`，并标记 run terminal。
- 覆盖 SSE `after` replay 能返回已持久化的 delta events。
- 覆盖前端 delta 追加、final 消息兼容、重连游标和错误态。

### 本地联调

```bash
docker run -d --name cqa-postgres-13 \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=change_quality_agent \
  -p 5432:5432 \
  postgres:13

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/change_quality_agent \
  uv run alembic upgrade head

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/change_quality_agent \
  uv run fastapi dev --host 127.0.0.1 --port 8000

cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

## 优化项

| 优先级 | 方案 | 内容 | 收益 | 代价 | 触发条件 |
| --- | --- | --- | --- | --- | --- |
| P2 | 方案 2：内存广播 + DB 持久化双写 | executor 收到 chunk 后同时写入 `run_events`，并推送到进程内 pub/sub queue；SSE 先 replay DB，再监听 queue。 | 降低观察端延迟，避免固定轮询间隔带来的 100ms-500ms 级延迟。 | 引入队列生命周期、断线清理、多订阅者 fan-out 等复杂度；多 worker 场景需要 Redis、Postgres notify 或类似跨进程通道。 | 方案 1 已上线且确认数据库轮询延迟影响体验，或产品明确需要更接近实时的 token 级显示。 |
