# Run Events Real Streaming TODO

## 优化项

| 优先级 | 方案 | 内容 | 收益 | 代价 | 触发条件 |
| --- | --- | --- | --- | --- | --- |
| P2 | 方案 2：内存广播 + DB 持久化双写 | executor 收到 chunk 后同时写入 `run_events`，并推送到进程内 pub/sub queue；SSE 先 replay DB，再监听 queue。 | 降低观察端延迟，避免固定轮询间隔带来的 100ms-500ms 级延迟。 | 引入队列生命周期、断线清理、多订阅者 fan-out 等复杂度；多 worker 场景需要 Redis、Postgres notify 或类似跨进程通道。 | 方案 1 已上线且确认数据库轮询延迟影响体验，或产品明确需要更接近实时的 token 级显示。 |
