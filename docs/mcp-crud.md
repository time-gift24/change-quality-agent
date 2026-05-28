# MCP CRUD 与运行时管理

本文档说明当前后端 MCP 管理能力。它取代临时设计/实施 plan，用于后续前端 MCP 管理页和 ReAct agent 配置接入时参考。

## 目标

MCP 管理模块负责把 MCP server 配置持久化到数据库，并由 FastAPI 进程内的 `McpRuntimeManager` 管理 stdio MCP 会话生命周期。当前版本可以完成：

- 注册、查看、更新、删除 MCP server 配置。
- 启动、停止、重启、检查 stdio MCP server。
- 初始化 MCP session 并通过 `tools/list` 发现工具。
- 持久化最近一次成功的工具快照。
- 在 API 响应中隐藏 `env` 和 `headers` 的敏感值。
- 在应用启动时恢复 `enabled=true` 且 `desired_state=running` 的 server。

## 模块边界

后端 MCP 域与 SOP run 和未来 ReAct agent 域保持隔离：

- `app/api/v1/mcp.py` 只处理 HTTP 输入、权限、响应和错误映射。
- `app/schemas/mcp.py` 定义请求/响应模型和字段校验。
- `app/models/mcp.py` 定义数据库模型。
- `app/repositories/mcp_servers.py` 负责 server 与 tool snapshot 持久化。
- `app/services/mcp_runtime.py` 负责 stdio session、生命周期状态和并发锁。
- `app/api/deps.py` 组装 repository、runtime manager、管理员用户校验。
- `app/main.py` 在 lifespan 中启动和关闭 MCP runtime。
- `api/openapi.yml` 是前后端共享 API 契约。

路由层不直接启动子进程；agent 运行也不直接保存 MCP 进程配置。MCP server 是共享运行时资源，agent 只是引用和消费它们。

## 数据模型

### `mcp_servers`

`mcp_servers` 是 MCP 配置和用户可见运行时快照的持久化来源。

核心字段：

- `id`: server ID。
- `name`: 唯一名称。
- `transport`: `stdio` 或 `http`。当前仅实现 `stdio` 生命周期，`http` 作为 schema 预留。
- `command`: stdio 启动命令。
- `args`: stdio 参数数组。
- `env`: stdio 环境变量。
- `url`: HTTP transport URL 预留字段。
- `headers`: HTTP transport header 预留字段。
- `enabled`: 是否允许应用启动时自动恢复。
- `desired_state`: 用户期望状态，取值 `running` 或 `stopped`。
- `runtime_status`: 当前进程视角的运行状态，取值 `unknown`、`starting`、`running`、`stopping`、`stopped`、`error`。
- `last_checked_at`: 最近一次检查或生命周期更新的时间。
- `last_error`: 脱敏后的短错误信息。

约束与索引：

- `name` 唯一。
- `(enabled, desired_state)` 索引用于启动恢复。

### `mcp_server_tools`

`mcp_server_tools` 保存最近一次成功发现的工具快照。

核心字段：

- `server_id`: 关联 `mcp_servers.id`，级联删除。
- `name`: 工具名。
- `description`: 工具说明。
- `input_schema`: MCP 工具入参 JSON Schema。
- `discovered_at`: 发现时间。

工具快照采用整组替换策略。`check` 或 `start` 失败不会删除上一份成功快照。

## API

所有 MCP 管理 API 都需要已认证的管理员用户 Cookie。缺少或无效用户 session 返回 `401`；普通用户返回 `403`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/mcp/servers` | 列出 server，返回脱敏配置、运行状态、tool count。 |
| `POST` | `/api/mcp/servers` | 创建 server 配置。 |
| `GET` | `/api/mcp/servers/{server_id}` | 查看单个 server 和最新工具快照。 |
| `PATCH` | `/api/mcp/servers/{server_id}` | 更新配置。server 正在运行或存在 live handle 时返回 `409`。 |
| `DELETE` | `/api/mcp/servers/{server_id}` | 删除配置。如果 server 正在运行，先停止再删除。 |
| `POST` | `/api/mcp/servers/{server_id}/start` | 设置 `desired_state=running` 并启动 server。 |
| `POST` | `/api/mcp/servers/{server_id}/stop` | 设置 `desired_state=stopped` 并停止 server，操作幂等。 |
| `POST` | `/api/mcp/servers/{server_id}/restart` | 停止后再启动，最终期望状态为 `running`。 |
| `POST` | `/api/mcp/servers/{server_id}/check` | 刷新工具和状态，不改变 `desired_state`。 |

生命周期接口统一返回：

- `server_id`
- `desired_state`
- `runtime_status`
- `last_checked_at`
- `last_error`
- `tool_count`

## 状态语义

`desired_state` 和 `runtime_status` 不表达同一件事：

- `desired_state` 是用户或系统希望 server 处于的目标状态。
- `runtime_status` 是当前 FastAPI 进程实际观察到的运行状态。

常见状态流转：

```text
unknown -> starting -> running
unknown -> starting -> error
stopped -> starting -> running
running -> stopping -> stopped
running -> error
error -> starting -> running
```

如果数据库显示 server running，但当前进程没有 live handle，runtime manager 会在下一次生命周期操作中按当前进程事实重新协调。

## 运行时生命周期

`McpRuntimeManager` 在 FastAPI lifespan 中创建并复用。它维护内存 map：

```text
server_id -> live MCP runtime handle
```

### Start

1. 校验 `mcp_runtime_single_instance`。
2. 获取 server 级别锁，避免并发生命周期操作和配置变更交错。
3. 加载 server 配置。
4. 校验 transport 和 stdio 启动策略。
5. 设置 `desired_state=running`。
6. 如果 live handle 已存在，返回 running 状态。
7. 设置 `runtime_status=starting`。
8. 使用 MCP Python SDK 启动 stdio client 并初始化 `ClientSession`。
9. 调用 `tools/list`。
10. 替换工具快照。
11. 设置 `runtime_status=running`，清空 `last_error`。

### Stop

1. 获取 server 级别锁。
2. 设置 `desired_state=stopped`。
3. 设置 `runtime_status=stopping`。
4. 如果存在 live handle，关闭 MCP session 和 stdio client。
5. 移除 live handle。
6. 设置 `runtime_status=stopped`。

Stop 对没有 live handle 的 server 是幂等的。

### Restart

`restart` 在同一把 server 锁内执行 `stop` 和 `start`，避免中间被配置更新或删除插入。

### Check

`check` 不改变 `desired_state`：

- 如果 server 已运行，复用 live session 调用 `tools/list`。
- 如果 server 未运行，创建临时 MCP session，发现工具后关闭临时 session。
- 成功时替换工具快照并更新 `last_checked_at`。
- 失败时记录脱敏 `last_error`，保留上一份成功工具快照。

### Startup 与 Shutdown

应用启动时，runtime manager 查询：

```text
enabled=true AND desired_state='running'
```

并尝试逐个启动。默认 `mcp_runtime_single_instance=false`，未显式确认单进程所有权时，启动恢复会 fail closed，并把目标 server 标记为 `error`。

应用关闭时，runtime manager 会关闭所有 live handles，并把对应 server 标记为 `stopped`；如果关闭失败，保留 handle 以便后续诊断或重试。

## 安全与运维配置

当前实现把 MCP 子进程管理作为高权限后台能力处理：

- 管理 API 必须通过用户 Cookie 鉴权，且当前用户必须是管理员。
- stdio 启动使用 `command` 和 `args` 数组，不接受 shell 命令字符串。
- `mcp_allowed_stdio_commands` 限制可执行命令。
- `mcp_allowed_stdio_specs` 限制可启动的 `command:first_arg` 组合，例如 `uvx:mcp-server-filesystem`。
- `mcp_runtime_single_instance` 默认 `false`，只有确认部署为单进程 owner 时才设为 `true`。
- API 响应中的 `env` 和 `headers` 值统一显示为 `********`。
- runtime 失败写入 `last_error` 前会脱敏 server secret、bearer token 和常见 secret assignment。
- lifecycle API 对外隐藏原始异常，统一返回受控错误文案。

暂未实现 secret 字段加密、HTTP MCP lifecycle、跨 worker 协调和 runtime 日志流。

## ReAct Agent 接入边界

后续 ReAct agent CRUD 应保存 agent blueprint 和 MCP server 引用，不应复制 MCP process config，也不应直接实例化 MCP session。

建议 agent 相关表只保存：

- agent 可使用的 `mcp_servers.id` 列表。
- run 创建时是否允许自动启动引用的 MCP server。
- agent 级工具 allowlist/denylist。
- 工具别名和描述覆盖。
- 工具调用权限策略。

run 实例化时的推荐流程：

```text
load react agent config
-> resolve referenced MCP servers
-> ensure servers are running, if policy allows
-> read latest tool snapshot or live tools/list
-> apply agent-level tool filters
-> namespace tools by server
-> wrap MCP tools as agent-callable tools
-> instantiate the ReAct graph
-> record resolved MCP/tool snapshot in run metadata
```

工具命名应带 server namespace，避免不同 MCP server 里同名工具冲突：

```text
{server_name}.{tool_name}
```

## 测试覆盖

当前 PR 覆盖：

- MCP schema 校验和响应脱敏。
- SQLAlchemy model 和 migration shape。
- repository CRUD、工具快照替换、cascade delete。
- 管理 API 的鉴权、CRUD、生命周期错误映射、并发锁。
- runtime start/stop/restart/check、startup 恢复、shutdown 清理、timeout、错误脱敏。
- 真实 FastMCP stdio echo server 集成测试。
- OpenAPI contract 与 `api/openapi.yml` 同步校验。

## 当前未做

- HTTP MCP lifecycle。
- 多 FastAPI worker 协调同一 MCP 子进程。
- runtime stdout/stderr 持久化或流式查看。
- secret 字段数据库加密。
- ReAct agent 表结构和 CRUD。
- SOP run 或 ReAct run 实际调用 MCP tools。
