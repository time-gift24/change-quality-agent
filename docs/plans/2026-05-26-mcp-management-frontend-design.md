# MCP 管理前端页面设计

日期：2026-05-26  
分支：`codex/mcp-frontend-design`

## 1. 目标与范围

基于现有后端 MCP 能力（CRUD + lifecycle + tools snapshot），在前端新增可运营的 MCP 管理页面，满足以下首版目标：

1. 在现有应用左侧导航中新增 MCP 管理入口。
2. 使用标准前端路由承载 MCP 页面。
3. 支持 MCP server 的创建、查看、更新、删除。
4. 支持生命周期操作：start / stop / restart / check。
5. 支持查看工具快照（tools snapshot）。
6. 为“仅管理员可访问”预留路由保护结构。

## 2. 约束与设计原则

1. 遵循 YAGNI：仅交付首版必要能力，不引入批量操作、日志流、自动轮询等扩展功能。
2. 遵循 KISS：保持与现有前端 `features/*` 分层一致，避免额外状态管理框架。
3. 遵循 DRY：复用 `lib/apiClient.ts` 的请求与错误处理。
4. UI 实现必须遵循根目录 `DESIGN.md`。
5. 与后端契约严格对齐 `api/openapi.yml` 与 `app/schemas/mcp.py`。

## 3. 路由与页面架构

采用方案 2（标准前端路由）：

1. `/sop`：现有 SOP 质检页面。
2. `/mcp`：新增 MCP 管理页面。
3. `*`：重定向到 `/sop`。

新增 `AppShell` 统一承载：

1. 左侧导航（保留“质量检查”，新增“MCP 管理”）。
2. 主内容区域通过 `Outlet` 渲染路由页面。

新增 `ProtectedRoute` 包裹 `/mcp`：

1. 首版用可替换的 `useAuthz()` 抽象（默认返回管理员可访问）。
2. 非管理员进入 `/mcp` 时渲染 403 占位页面。
3. 后续管理员规则落地时，仅替换 `useAuthz()` 实现。

## 4. MCP 页面布局设计（前端布局）

`/mcp` 页面采用“两栏工作台”布局：

1. 顶部栏：页面标题 + “新增 MCP Server”按钮。
2. 左栏（约 35% 或固定 360px）：MCP Server 列表（核心）。
3. 右栏（约 65%）：当前选中 server 的详情与编辑。

左栏包含：

1. 搜索框（按 name 过滤）。
2. 状态筛选（runtime_status）。
3. 列表项字段：`name`、`runtime_status`、`desired_state`、`tool_count`。
4. 行内快捷操作：`start`、`stop`、`restart`、`check`。

右栏包含：

1. 状态卡片：`runtime_status`、`desired_state`、`last_checked_at`、`last_error`。
2. `Configuration` 标签页：配置查看与编辑。
3. `Tools Snapshot` 标签页：工具名称、描述、`input_schema`。
4. 底部操作：`保存修改`、`删除 Server`（二次确认）。

新增/编辑交互：

1. 点击“新增 MCP Server”打开抽屉（Drawer）表单。
2. transport 联动校验：
   - `stdio` 必填 `command`
   - `http` 必填 `url`
3. 提交成功后刷新列表并选中目标 server。

## 5. 数据流与状态管理

### 5.1 模块分层

新增 `features/mcp`：

1. `types.ts`：MCP 类型定义（与后端 schema 对齐）。
2. `api.ts`：MCP API 调用函数（list/get/create/update/delete/lifecycle）。
3. `hooks.ts`：查询与 mutation hooks。
4. `pages/McpPage.tsx`：MCP 页面入口。
5. `components/*`：列表、详情、表单、工具快照等子组件。

### 5.2 页面状态最小集

1. `selectedServerId`
2. `searchText`
3. `statusFilter`
4. `isCreateDrawerOpen`
5. `editingDraft`
6. `pendingAction`

### 5.3 刷新策略

1. 列表作为主数据源。
2. mutation 成功后执行：`refetch list`。
3. 若有选中项，额外 `refetch detail`。
4. 生命周期操作不做 optimistic update，避免状态误判。

## 6. API 对齐与错误处理

### 6.1 首版覆盖 API

1. `GET /api/mcp/servers`
2. `POST /api/mcp/servers`
3. `GET /api/mcp/servers/{server_id}`
4. `PATCH /api/mcp/servers/{server_id}`
5. `DELETE /api/mcp/servers/{server_id}`
6. `POST /api/mcp/servers/{server_id}/start`
7. `POST /api/mcp/servers/{server_id}/stop`
8. `POST /api/mcp/servers/{server_id}/restart`
9. `POST /api/mcp/servers/{server_id}/check`

### 6.2 错误语义

1. `409`（更新冲突）：提示“请先停止服务再修改配置”。
2. `404`（目标不存在）：提示并清空当前选中项。
3. `502/503`（生命周期失败）：提示失败并建议执行 check。
4. 页面级加载失败提供重试入口。

### 6.3 脱敏与安全展示

1. `env` / `headers` 在详情中仅展示后端脱敏值（`********`）。
2. 首版不提供 secret 明文回显。
3. 对“编辑即覆盖”给出明确文案。

## 7. 测试策略

单测最小完整覆盖：

1. `features/mcp/api.test.ts`：接口与错误映射。
2. `features/mcp/hooks.test.tsx`：加载、刷新、mutation 状态。
3. `features/mcp/pages/McpPage.test.tsx`：列表、选中、tab、冲突提示。
4. `app/routing/ProtectedRoute.test.tsx`：管理员/非管理员路径。

首版不引入额外 e2e 作为必选项。

## 8. 非目标（首版明确不做）

1. 批量 start/stop/restart/check。
2. 实时日志流（stdout/stderr）。
3. 自动轮询和状态变化动画。
4. 真正管理员鉴权逻辑（仅预留 guard）。
5. HTTP transport 生命周期扩展。

## 9. 落地文件变更计划

1. `frontend/src/app/App.tsx`
2. `frontend/src/app/AppShell.tsx`（新增）
3. `frontend/src/app/routing/ProtectedRoute.tsx`（新增）
4. `frontend/src/features/mcp/**`（新增）
5. `frontend/src/features/sop/pages/ChatPage.tsx`（按路由接入最小调整）

## 10. 验收标准

1. 用户可从左侧导航进入 `/mcp`。
2. 可完成 server 的增删改查。
3. 可执行 start/stop/restart/check。
4. 可查看 tools snapshot。
5. `/mcp` 已被保护路由包裹，具备后续管理员策略接入点。
6. 新增前端测试通过。
