# MCP 管理页 — 表格化重构与详情子路由

## 目标

将 `/mcp` 从「左卡片列表 + 右卡片详情」的双面板结构改为「shadcn 风格表格 + 独立详情页」，配套面包屑导航与 shadcn 风格表单抽屉。所有视觉与 token 沿用 `frontend/DESIGN.md`，不引入新的颜色 / 字号 / 阴影系统。

不在范围：后端 API 变更、权限模型变更、分页/虚拟滚动 (留 hook，不实现)。

> **Spec v2 修订说明**：以下章节根据 spec-document-reviewer 反馈在 §URL 状态机、§可用 token 与 StatusBadge、§表单错误展示、§Row 交互与键盘、§详情页头加载态、§Drawer 路由归属、§测试迁移矩阵 处做了细化。

## 路由

新增嵌套路由：

```
/mcp                      → McpListPage     (表格视图)
/mcp/new                  → McpListPage + create drawer 打开
/mcp/:serverId            → McpDetailPage   (详情页，tabs: 配置 | 工具快照)
/mcp/:serverId/edit       → McpDetailPage + edit drawer 打开
```

- `useNavigate()` + `useParams()` 驱动跳转，browser back / refresh 可用。
- `WorkspaceSidebar` 在 `pathname === '/mcp' || pathname.startsWith('/mcp/')` 时 `activeKey="mcp"` (避免误伤未来的 `/mcp-anything`)。
- Tab 状态通过 `useSearchParams()` 保存：`/mcp/:id?tab=tools` 可分享。
- `McpServerFormDrawer` 继续作为抽屉组件，但 `open` 由路由派生 (`/mcp/new` 或 `/mcp/:id/edit`)，关闭即 `navigate(parentPath)`。

`App.tsx` 路由表新增：

```tsx
<Route path="/mcp" element={<McpListPage />}>
  <Route path="new" element={null} />
</Route>
<Route path="/mcp/:serverId" element={<McpDetailPage />}>
  <Route path="edit" element={null} />
</Route>
```

### URL 状态机

抽屉的 `open` 由 `useMatch('/mcp/new')` / `useMatch('/mcp/:serverId/edit')` 在各自页面内派生。**Drawer 不下沉到 layout route**，列表页负责 `/mcp/new`，详情页负责 `/mcp/:id/edit`。这样两个 drawer 实例在路由层互斥 (用户不可能同时位于两条路径)，不会出现共享 `useMcpMutations()` 状态冲突。

| 触发动作 | 当前路径 | 下一路径 | 副作用 |
|---|---|---|---|
| 点击 `+ 新增 Server` | `/mcp` | `/mcp/new` | 列表页打开 create drawer |
| Drawer 关闭 / 取消 / Esc | `/mcp/new` | `/mcp` | search 不需保留 |
| 创建成功 | `/mcp/new` | `/mcp/:newId` | `refetchServers()`；落地新建服务详情页，更连贯 |
| 创建失败 | `/mcp/new` | `/mcp/new` | drawer 保持，顶部 `role="alert"` 渲染 API 错误 |
| 行点击 | `/mcp` | `/mcp/:id` | `useMcpServerDetail(:id)` 触发首拉 |
| `⋯ 编辑` 或详情页头 `编辑` | `/mcp/:id` | `/mcp/:id/edit?...` | drawer 打开，保留 `?tab=`；如详情 404 则直接 `navigate('/mcp', { replace: true })` |
| Drawer 关闭 (edit) | `/mcp/:id/edit` | `/mcp/:id` | 关闭时 `navigate({ pathname: '/mcp/:id', search: location.search })` 保留 tab |
| 更新成功 | `/mcp/:id/edit` | `/mcp/:id` | `refetchServers() + refetchDetail()` |
| `⋯ 删除` (列表) | `/mcp` | `/mcp` | `refetchServers()`；若删除当前列表已无项目，渲染空态 |
| 详情头 `删除` | `/mcp/:id` | `/mcp` (replace) | `refetchServers()`；**不调用** `refetchDetail`，避免对已删服务再发请求 |
| 详情 404 | `/mcp/:id` | `/mcp/:id` (不跳) | tab 区域渲染 "MCP 服务不存在" + `返回列表` 按钮；URL 保持，浏览器后退仍能离开 |
| `/mcp/:id/edit` 直链 + 详情 404 | `/mcp/:id/edit` | `/mcp` (replace) | drawer 无 seed 数据不可工作，直接跳列表 |
| 详情 mutation 返回 404 (`isMcpNotFoundError`) | `/mcp/:id` | `/mcp/:id` | 顶部 alert 显示错误；触发 `refetchServers() + refetchDetail()` 让用户看到 "服务不存在" 卡片 |
| 列表 row mutation 返回 404 | `/mcp` | `/mcp` | 顶部 alert + `refetchServers()`；**不导航** |
| `Admin Token` 保存 | 任意 | 同上 | `refetchServers()`；如在详情页且有 `serverId`，并行 `refetchDetail()` |

### 直链与加载竞态

- `/mcp/:serverId` 直链：`useMcpServerDetail` 首拉前 `detail.data === null && loading === true`。详情页 H1 在加载期渲染 `<span className="font-mono text-xs text-mute">{serverId}</span>` 骨架占位；StatusBadge 显示 `unknown`；操作按钮 disabled。
- `/mcp/new` 直链：列表页正常渲染骨架行 + drawer 覆盖在上层。drawer 不依赖列表数据。
- `useSearchParams` tab 状态：`?tab=tools` 无效值 (非 `configuration`/`tools`) 回退到 `configuration`，不写回 URL。

### Drawer 归属与共享

- `useMcpMutations()` 已确认是「每实例独立 state」(`useState` 在 hook 内部)，列表页 mutation 与详情页 mutation 的 pending/error 互不影响 — 这是预期的，列表 row 操作的 pending 不应该让详情页的「编辑」disabled。
- `useMcpServerDetail.refetch` 闭包了当前 `serverId`，重新调用即刷新当前 `serverId` 数据，无需手动重绑。
- 列表页同时持有 `useMcpServers` + 自己的 `useMcpMutations()`；详情页持有 `useMcpServerDetail(serverId)` + 自己的 `useMcpMutations()`。两套 hook 实例并存不会互相干扰。

## 列表页 `McpListPage`

### 整体容器

- 沿用 `WorkspaceSidebar` + main 布局，main padding `px-4 py-3` 与 ChatPage 一致。
- 顶部紧凑 header：`text-base font-semibold` 标题 `MCP 管理` + `text-xs text-mute` 副标题。Admin Token 控件保留在 header 右侧。
- 内容区为「单张外框 table」：`rounded-xl border border-hairline bg-canvas` 包住整个 toolbar + table + footer，**不再有左右两张卡片**。

### Toolbar

`flex items-center gap-2 px-3 py-2 border-b border-hairline`

| 控件 | 样式 |
|---|---|
| 搜索 | `h-9 w-64 rounded-lg border border-hairline bg-canvas pl-9 pr-3 text-xs` + 左侧 search 图标，placeholder `按名称搜索…` |
| 状态筛选 | `h-9 rounded-lg border border-hairline bg-canvas px-3 text-xs` (native select + `appearance-none` + chevron) |
| 刷新 (右对齐) | `h-9 rounded-lg border border-hairline bg-canvas px-3 text-xs hover:border-hairline-strong` |
| `+ 新增 Server` (右对齐) | `h-9 rounded-lg bg-primary text-on-primary px-3 text-xs font-medium hover:bg-primary-deep` → `navigate('/mcp/new')`；**`aria-label="新增 MCP Server"`** (沿用现有测试 `getByRole("button", { name: "新增 MCP Server" })` 查询字符串) |

### Table

`<table className="w-full text-sm">`

**Header** — `bg-canvas-soft border-b border-hairline`，`<th>` 单元格：
`h-10 px-3 text-left text-2xs font-medium uppercase tracking-wide text-mute font-mono`

| 列 | 宽度 | 内容 |
|---|---|---|
| 名称 | flex | `text-sm font-medium text-ink` + 下方 `text-2xs text-mute font-mono` 的 transport |
| 状态 | 120px | `<StatusBadge>` — `inline-flex h-5 items-center gap-1 rounded-full px-2 text-2xs`，颜色按 status |
| 工具 | 80px | `text-2xs tabular-nums font-mono` |
| 最近检查 | 160px | 相对时间 `text-2xs text-mute`，`-` 表示从未检查 |
| 操作 | 56px | `⋯` icon button → dropdown |

**Body 行**：
- `border-b border-hairline last:border-0 hover:bg-canvas-soft transition-colors`
- **名称列是真正的链接**：`<td><Link to={`/mcp/${id}`} className="block focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30">…</Link></td>`。这样：原生右键 "新标签页打开" 可用；屏幕阅读器读出 "link"；不再有「整行 cursor-pointer + 嵌套 button」反模式。
- 其它列普通展示，无 click handler；StatusBadge / 工具数 / 最近检查 / 操作均为 inert text。
- `⋯` trigger button：`onClick={(e) => e.stopPropagation()}` (防御性) — 由于行本身不再有 click handler，主要为后续可能改回行 click 的兼容；当前不依赖此行为。

**StatusBadge 颜色** (仅使用 `globals.css` 已存在的 token：`--color-success / --color-error / --color-error-soft / --color-error-deep / --color-canvas-soft / --color-mute / --color-hairline-strong / --color-primary / --color-primary-soft / --color-ink`)：

| status | pill 背景 | pill 文字 | 圆点 |
|---|---|---|---|
| running | `bg-success/15` | `text-success` | `bg-success` |
| stopped | `bg-canvas-soft` + `border border-hairline` | `text-body` | `bg-hairline-strong` |
| error | `bg-error-soft` | `text-error-deep` | `bg-error` |
| starting / stopping | `bg-primary-soft` | `text-primary-deep` | `bg-primary` |
| unknown | `bg-canvas-soft` + `border border-hairline` | `text-mute` | `bg-hairline-strong` |

不引入 `success-deep`。所有颜色 class 在当前 `globals.css` 已定义。

### Row action dropdown

自实现轻量 `<Menu>` (无 Radix)：
- `position: absolute` 锚到 trigger，`mt-1 right-0 w-44 rounded-lg border border-hairline bg-canvas shadow-md p-1 text-xs`
- **打开**：`Enter` / `Space` / `ArrowDown` on trigger → 打开 + 首项 focus。`ArrowUp` on trigger → 打开 + 末项 focus。鼠标点击：打开 + 首项 focus。
- **关闭**：`Escape`、点击 menu 外、选择条目；关闭时焦点回到 trigger。
- **导航**：`ArrowUp/Down` 循环切换 (跳过 disabled 项与分隔符)，`Home/End` 跳首末，`Enter`/`Space` 触发当前项。
- **不实现 typeahead** (v1 范围外)。
- **不实现 viewport flip**：菜单可能在表格底部裁切，v1 接受；用户可滚动后展开。
- ARIA：trigger `aria-haspopup="menu" aria-expanded`；menu `role="menu" aria-labelledby={triggerId}`；项 `role="menuitem"`。
- 由于名称列已是 link，trigger 上的 `Enter` 不会冒泡触发行链接 (它不再是 click handler 持有者)，无需 stopPropagation；但仍添加 `event.preventDefault()` 防止 `Space` 引起页面滚动。

菜单项 (按 runtime_status 动态裁剪 start/stop)：
```
查看详情
编辑
──────────
启动     (仅 stopped / error / unknown)
停止     (仅 running / starting)
重启
检查
──────────
删除                  (text-error-deep)
```

### 空 / 加载 / 错误 / 底部

- 加载：tbody 一行单元格 `py-8 text-center text-xs text-mute` "加载中…"
- 错误：tbody 上方一行 `border border-error-soft bg-canvas px-3 py-2 text-xs text-error-deep`，table 仍渲染 (可能有缓存数据)
- 空：tbody 一行单元格 `py-12 text-center text-xs text-mute` "暂无 MCP 服务，点击 + 新增 Server 开始添加。" + 内嵌主按钮
- Footer：`flex items-center justify-between border-t border-hairline px-3 py-2 text-2xs text-mute font-mono` — 左：`共 N 个服务` (筛选时 `· 显示 M 个`)；右：`全部加载` (`text-2xs text-mute`，v1 不实现分页；不预留空区，避免审美死区)

## 详情页 `McpDetailPage`

### 顶部 strip

`flex shrink-0 flex-col gap-3 border-b border-hairline bg-canvas/60 px-4 py-3 backdrop-blur-sm`

**面包屑** (`<nav aria-label="面包屑">`)：
- mono caption，`text-2xs`
- `<Link to="/mcp">` "MCP 管理" `text-mute hover:text-ink`
- 分隔 `›` `text-mute`
- 当前段：服务名 `text-ink font-medium`，长度过长则 `truncate max-w-[24ch]`

**页头行** (`flex items-start justify-between gap-3`)：
- 左：`<h1>` 服务名 `text-base font-semibold tracking-tight text-ink`；下方 `text-2xs text-mute` `<StatusBadge>` + ` · transport · desired {state}`
  - 加载态 (`detail.loading && !detail.data`)：H1 渲染 `serverId`，类名 `font-mono text-base text-mute`；副行只渲染 `<StatusBadge status="unknown" />`；其它分段不渲染
  - 404 态：H1 渲染 `serverId` (灰)；副行不渲染
- 右：`编辑` (h-9 ghost) · `删除` (h-9 destructive ghost) · `⋯` 触发与 row 相同的动作 dropdown (Start/Stop/Restart/Check)
  - 加载/404 态：右侧三个控件 disabled (`aria-disabled="true"`)

### Tab bar

`border-b border-hairline px-4`，`<div role="tablist">` 两个 tab：

| Tab | aria-controls | 内容 |
|---|---|---|
| `配置` | `mcp-detail-config-panel` | definition table |
| `工具快照 (N)` | `mcp-detail-tools-panel` | tools 表格 |

Tab 按钮：`h-9 px-3 text-xs font-medium`，inactive `text-mute hover:text-ink`，active `text-ink shadow-[inset_0_-2px_0_var(--color-primary)]`。

URL 同步：`useSearchParams()` `tab=tools` ↔ activeTab。

### 配置 panel

单张外框 `rounded-xl border border-hairline bg-canvas`，内部为定义行：

```
grid grid-cols-[160px_minmax(0,1fr)] gap-3 border-b border-hairline px-4 py-2.5 last:border-0
```

- 标签：`text-2xs uppercase tracking-wide text-mute font-mono`
- 值：`text-xs text-ink break-all`；code-like 值 (command/args/env/headers) 用 `font-mono text-2xs`

行集合：Transport / Command / URL / Args / Enabled / Desired State / Env / Headers。
Env / Headers 多条时，值列垂直堆叠 `space-y-0.5`。

如有 `last_error`，在 dl 之前插入 `<p role="alert" className="rounded-lg border border-error-soft bg-canvas px-3 py-2 text-xs text-error-deep mb-3">`。

### 工具快照 panel

`<table>` 嵌入相同 `rounded-xl border border-hairline bg-canvas`：

| 列 | 宽度 | 内容 |
|---|---|---|
| 工具名 | 240px | `font-mono text-xs text-ink` |
| 描述 | flex | `text-xs text-body` |
| Schema | 120px | `查看 schema ▾` 按钮 |

点击 Schema → 行下方展开 `<pre className="bg-canvas-soft font-mono text-2xs px-3 py-2">JSON.stringify(input_schema, null, 2)</pre>` (在同一个 `<tr>` colspan 行)。

空：`py-12 text-center text-xs text-mute` "暂无工具快照。"

### 状态处理

- 整页 loading：tab 内容区域 `text-xs text-mute` "加载详情中…"
- 404 (`isMcpNotFoundError(detailState.error)`)：tab 区域居中卡片 — "MCP 服务不存在" + `返回列表` 按钮 → `navigate('/mcp', { replace: true })`
  - **UX 决策说明**：选择「留在 URL + 手动返回」而非「自动跳回」是因为：用户可能通过书签 / 链接进入，自动跳转会丢失 URL 上下文且无法浏览器后退到 404 前的页面。显示明确的「不存在 + 返回」是更诚实的做法。当前实现的 `useEffect` 自动跳回在新设计中被移除，对应测试用例 (`clears selected server after detail returns 404`) 改写为验证 404 卡片渲染 + 点击 `返回列表` 后跳转。
- 删除成功 → `navigate('/mcp', { replace: true })` + `refetchServers()`；**不调用 refetchDetail** (避免请求已删服务)
- 任何 mutation 出错：顶部 alert (沿用现有 `getMcpErrorMessage` 文案)

## 表单抽屉 (shadcn-form 风格，紧凑)

抽屉外壳保留 (焦点陷阱、Esc 关闭、Tab wrap 测试不变)，仅内部重排。

### Drawer chrome

- 宽度：`w-full sm:w-[420px]`
- Header：`flex items-center justify-between border-b border-hairline px-4 py-3` — 标题 `text-sm font-semibold text-ink`；下方 `text-2xs text-mute font-mono` 显示 `NEW SERVER` / `EDIT · {server.id}`
- Body：`flex-1 overflow-y-auto px-4 py-3 space-y-3`
- Footer：`sticky bottom-0 flex items-center justify-end gap-2 border-t border-hairline bg-canvas px-4 py-3` — `取消` (h-9 ghost) + `保存` (h-9 primary)

### Section 分组

每个 section header：

```tsx
<h3 className="mt-4 first:mt-0 mb-2 pb-1.5 border-b border-hairline text-2xs font-mono uppercase tracking-wide text-mute">
  基本信息
</h3>
```

分组：
1. **基本信息** — 服务名称、传输方式
2. **连接** — command + args (stdio) / url (http) — 条件渲染
3. **环境与请求头** — env、headers
4. **启动行为** — `创建后立即启动` (desired_state checkbox) + `启用` (enabled checkbox)

### Field primitive

每个字段：

```tsx
<div className="space-y-1">
  <label htmlFor={id} className="text-xs font-medium text-ink">
    服务名称 <span className="text-error">*</span>
  </label>
  <input
    id={id}
    aria-invalid={!!error}
    aria-describedby={error ? errorId : helperId}
    className="h-9 w-full rounded-lg border border-hairline bg-canvas px-3 text-xs text-ink placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 aria-invalid:border-error aria-invalid:ring-error/20 disabled:cursor-not-allowed disabled:opacity-50"
  />
  {error
    ? <p id={errorId} className="text-2xs text-error-deep">{error}</p>
    : helper ? <p id={helperId} className="text-2xs text-mute">{helper}</p> : null}
</div>
```

Textarea: `min-h-[72px] py-2 font-mono text-2xs leading-relaxed resize-y` (其他同上)。
Select: 同 Input + `appearance-none` + 绝对定位 chevron。

### Validation

- 提交时校验，第一项错误字段 auto-focus
- 用户编辑该字段时清除其错误
- **错误展示分两类，互斥渲染，避免 `getByRole("alert")` 多匹配**：
  - **客户端字段级错误** — 每个字段下方渲染一个 `<p id={errorId} role="alert" className="text-2xs text-error-deep">`，**仅在该字段有错误时**渲染。submit 校验失败时，**不渲染顶部 alert 区** (保持 API 错误专用)。这样 `getByRole("alert")` 在 client-side 校验场景下唯一匹配到第一个 / 当前唯一的字段错误，与现有断言 `expect(within(dialog).getByRole("alert")).toHaveTextContent("请填写服务名称。")` 兼容 (单字段错误时仅一个 alert)。
  - **API 错误** — 顶部一个 `<p role="alert">`，**仅在** `mutations.error` 非空时渲染。此时字段级错误已被用户编辑清除 (否则不会触发新提交)，二者不并存。
- 多字段同时报错的情形：currently `validateForm` 找到第一个错误就 return false (沿用现有实现)；如果未来改为收集所有错误，将首字段错误用 `role="alert"`，其它用 `aria-live="polite"` 以避免多 alert 冲突。
- screen-reader 噪音：字段错误使用 `role="alert"` 在用户清除时不会被 announce (只在出现时 announce)，可接受。
- 校验文案完全不变，保留：
  1. "请填写服务名称。"
  2. "stdio 模式需要填写 command。"
  3. "请填写有效的 http url。"
  4. "env 第 1 行需要使用 KEY=VALUE 格式。" / "headers 第 N 行需要使用 KEY=VALUE 格式。"

### Checkbox 行

```tsx
<label className="flex items-start gap-2 cursor-pointer">
  <input type="checkbox" className="mt-0.5 h-4 w-4 rounded border-hairline bg-canvas accent-primary" />
  <span>
    <span className="text-xs text-ink">创建后立即启动</span>
    <span className="block text-2xs text-mute">服务保存后将立即拉起 (desired_state=running)</span>
  </span>
</label>
```

`desired_state` 从原 select 改为 checkbox (`true → "running"`, `false → "stopped"`)；`enabled` 同样改为 checkbox。

## 组件文件结构

```
src/features/mcp/
  pages/
    McpListPage.tsx       (新)
    McpListPage.test.tsx  (新；移植/重写当前 McpPage.test.tsx 中列表相关用例)
    McpDetailPage.tsx     (新)
    McpDetailPage.test.tsx(新)
  components/
    McpServerTable.tsx    (新；含 toolbar + table + footer + empty/loading)
    McpRowActionsMenu.tsx (新；shadcn 风格 dropdown，可被列表行与详情页头复用)
    McpStatusBadge.tsx    (新；从现 StatusDot 升级为带文字 pill)
    McpBreadcrumb.tsx     (新；简单两段面包屑)
    McpServerFormDrawer.tsx (改写为 shadcn 风格 form)
    McpDetailConfigPanel.tsx (新；definition table)
    McpDetailToolsPanel.tsx  (新；tools 表格 + schema 展开)
    AdminTokenControl.tsx (新；从现 McpPage.tsx 提取，列表页 header 用；如详情页 header 不复用则不放此处)
    errorMessages.ts      (沿用)
  hooks.ts                (沿用)
  adminToken.ts           (沿用)
  types.ts                (沿用)
```

`McpPage.tsx` 删除；旧 `McpServerList.tsx` / `McpServerDetail.tsx` 删除。

`AdminTokenControl` 提取为独立小组件复用于列表页 header (从现 `McpPage.tsx` 拆出)。详情页 header 不渲染 AdminTokenControl；如详情页 403 需恢复 token，404 卡片中的「返回列表」按钮即足够 — 用户在列表页输入 token 后重新进入。

## 状态管理与数据流

- 列表页：`useMcpServers()` + 本地 `searchText` / `statusFilter`；mutation 走 `useMcpMutations()`，成功后 `refetchServers()`；删除从 row dropdown 触发时如果当前没有详情页打开，直接刷新列表即可
- 详情页：`useParams<{serverId: string}>()` → `useMcpServerDetail(serverId)`；mutation 同上，成功后并行 `refetchServers() + refetchDetail()`
- 404 处理：详情页 `isMcpNotFoundError(detailState.error)` → 渲染「服务不存在」卡片 (而不是 `useEffect` 副作用跳回)；这样 URL 保留，用户主动点 `返回列表`
- 双页共享的 mutation 行为通过 `useMcpMutations()` hook 自然共用，无需提升状态

## 测试策略

保留并扩展。要点：

### 现有 `McpPage.test.tsx` → 新文件 迁移矩阵

| # | 现有用例 | 新位置 | 调整 |
|---|---|---|---|
| 1 | `renders mcp workspace through /mcp route` | `McpListPage.test.tsx` | 断言变为查找表格 thead / row |
| 2 | `renders the shared workspace sidebar with MCP marked active` | `McpListPage.test.tsx` | 无变化 |
| 3 | `keeps the server list and detail visible after toggling the sidebar` | 拆分：`McpListPage.test.tsx` 验证列表 + `McpDetailPage.test.tsx` 验证详情 | 删除原 region "MCP 服务详情" 断言；改为表格存在 + 单独详情页测试 |
| 4 | `renders server list in left panel` | `McpListPage.test.tsx` | 通过 `getAllByRole("row")` / `within(row).getByText(name)` |
| 5 | `switches right detail when clicking list item` | `McpListPage.test.tsx` + `McpDetailPage.test.tsx` | 列表测试：点击 `<Link>` 后 URL → `/mcp/srv-2`；详情测试：`MemoryRouter initialEntries={["/mcp/srv-2"]}` 渲染 detail header |
| 6 | `shows tools after switching to tools snapshot tab` | `McpDetailPage.test.tsx` | tab click → 渲染工具表；URL search 变为 `?tab=tools` |
| 7 | `invokes start stop restart check actions` | `McpListPage.test.tsx` | 改为打开 `⋯` dropdown 后选择各 menuitem；`getByRole("menuitem", { name: "启动" })`；保留 mutation 断言 |
| 8 | `shows clear Chinese message for 409 update conflicts` | `McpListPage.test.tsx` | 顶部 alert 文案不变 |
| 9 | `asks for confirmation before delete and restart` | `McpListPage.test.tsx` | 通过 `⋯ → 重启 / 删除` 触发；confirm 文案不变 |
| 10 | `does not confirm or delete while selected detail belongs to a previous server` | `McpDetailPage.test.tsx` | 改为：当 `detailState.data?.id !== serverId` 时 `编辑 / 删除` 按钮 disabled，点击无效 |
| 11 | `stores the MCP admin token and refetches the selected server data` | `McpListPage.test.tsx` | 详情 refetch 部分移除 (列表页没有详情)；仅断言 `refetchServers` 被调用 |
| 12 | `reloads failed list data after saving a non-empty admin token` | `McpListPage.test.tsx` | 同上 |
| 13 | `shows detail load errors before the empty selected state` | `McpDetailPage.test.tsx` | 改为：404 → "MCP 服务不存在" + 返回按钮；其它 detail error → 顶部 alert + 内容区错误状态 |
| 14 | `clears selected server after detail returns 404` | `McpDetailPage.test.tsx` | **行为变更**：不再 auto-redirect；改为「断言 404 卡片渲染 + 点击 `返回列表` 后 URL → `/mcp`」 |
| 15 | `keeps current detail when non-selected row mutation returns 404` | `McpListPage.test.tsx` | 行 mutation 404 → 顶部 alert 渲染 + `refetchServers` 调用 + 不导航 |
| 16 | `clears selected server on successful delete without refetching deleted detail` | `McpDetailPage.test.tsx` | 详情头删除 → `useNavigate` mock 收到 `/mcp` + `refetchServers` 调用 + `refetchDetail` **未**调用 |
| 17 | `shows inline error for empty name and prevents create` | `McpServerFormDrawer.test.tsx` | alert 现在是字段级 `role="alert"`，仍能命中 |
| 18 | `validates required command for stdio and closes drawer on Escape` | `McpServerFormDrawer.test.tsx` | 字段级 alert + Escape → URL 回到 `/mcp` |
| 19 | `validates invalid http url before submit` | `McpServerFormDrawer.test.tsx` | 字段级 alert 在 url 字段下 |
| 20 | `creates server with parsed args env headers and conservative defaults` | `McpServerFormDrawer.test.tsx` | payload 形状不变；额外断言成功后 URL → `/mcp/:newId` |
| 21 | `shows inline validation for malformed key value config lines` | `McpServerFormDrawer.test.tsx` | 字段级 alert |
| 22 | `omits unchanged redacted env and headers when updating` | `McpServerFormDrawer.test.tsx` | 通过 `/mcp/:id/edit` 路径渲染；payload 断言不变 |
| 23 | `wraps focus within drawer on Tab and Shift+Tab` | `McpServerFormDrawer.test.tsx` | 不变 |

### 新增测试文件

**`McpListPage.test.tsx`** (上表 1, 2, 3a, 4, 5a, 7, 8, 9, 11, 12, 15 迁移)：
- 表格 thead 列名渲染、tbody 行数 = filteredServers.length
- 行内名称是 `<Link>`：`expect(within(row).getByRole("link", { name: /Alpha Server/ })).toHaveAttribute("href", "/mcp/srv-1")`
- 状态筛选 / 搜索过滤后表格行数变化
- 空 / 加载 / 错误三态
- footer 计数文本
- `⋯` 菜单：键盘 (`ArrowDown` 打开并 focus 首项、`Escape` 关闭并 focus 回 trigger、`Home/End`)；点外关闭
- 菜单中根据 `runtime_status` 显示 `启动` 或 `停止`
- Admin Token (无详情 refetch)

**`McpDetailPage.test.tsx`** (上表 3b, 5b, 6, 10, 13, 14, 16 迁移)：
- `/mcp/srv-1` 渲染面包屑两段 (`<nav aria-label="面包屑">`)、H1 名称、StatusBadge
- 加载态：H1 显示 `serverId` 灰字 + 编辑/删除 disabled
- Tab 切换同步 `?tab=tools`；`?tab=tools` 直链直接打开工具 tab；非法 `?tab=foo` 回退 configuration (不改 URL)
- 配置面板渲染所有 dl 行；env/headers `********` 展示
- 工具表行 + `查看 schema` 展开 `<pre>`
- 404 → "MCP 服务不存在" + 返回列表按钮 → URL `/mcp`
- 删除成功 → mock `useNavigate` 收到 `/mcp` + `refetchServers` 调用 + `refetchDetail` 未调用
- 编辑按钮 → URL `/mcp/:id/edit`；Drawer 关闭后保留 `?tab=tools`
- `/mcp/:id/edit` + detail 404 → 自动 `navigate('/mcp', { replace: true })`

**`McpRowActionsMenu.test.tsx`** (新)：
- 键盘交互矩阵；ARIA `role="menu"`/`menuitem`；focus 还原
- 不依赖具体颜色 class

**`McpServerFormDrawer.test.tsx`** (上表 17–23 迁移)：
- per-field `role="alert"` 在字段下；`aria-describedby` 关联
- 首项错误 auto-focus
- 用户键入清除该字段错误
- Drawer 通过 `MemoryRouter initialEntries={["/mcp/new"]}` 或 `["/mcp/srv-1/edit"]` 渲染
- 关闭 (Esc / `取消`) → URL 回到父路径
- 创建成功 → URL `/mcp/:newId`
- 现有 4 条校验文案断言全部沿用
- payload 形状 / `********` 省略沿用

**`McpStatusBadge.test.tsx`** (新)：
- 通过 `data-status="running"` 等属性断言，避免 class 字符串硬编码
- 渲染快照 (HTML snapshot) 作为视觉回归 (可选)
- 不断言 Tailwind class 字符串

**App / 路由测试**：
- `/mcp/srv-1` 渲染详情页 (mock detail hook)
- `/mcp/new` → drawer 打开 (`role="dialog" name="新增 MCP 服务"`)
- `/mcp/srv-1/edit` → drawer 打开 (`role="dialog" name="编辑 MCP 服务"`)
- 关闭 drawer → URL 回到父路径

**`WorkspaceSidebar`** 测试沿用，无需修改 (`activeKey="mcp"` 仍然驱动)。

## 可访问性

- 表格：`<table>` 原生语义；行为 `role="row"`；操作按钮 aria-label 包含服务名 (沿用 `启动 ${name}` 等)
- StatusBadge：图标点 `aria-hidden`，文本作为可访问名称
- Dropdown：`role="menu"` + `role="menuitem"`、`aria-haspopup="menu"`、`aria-expanded`
- 面包屑：`<nav aria-label="面包屑">` + `<ol>` + 当前段 `aria-current="page"`
- Tab：`role="tablist" / "tab" / "tabpanel"`、`aria-controls`、`aria-selected`
- 表单：每个 input 有 `<label htmlFor>`，错误 `id` + `aria-describedby`，`aria-invalid`

## 响应式

- 列表 table 在 `< sm` 隐藏「最近检查」、「工具」列，仅保留 名称 / 状态 / 操作
- 详情页面包屑过长 → 名称段 `truncate max-w-[16ch] sm:max-w-[24ch]`
- Drawer 在 `< sm` 全屏 (`w-full`)，`sm+` 固定 420px

## 风险与权衡

- **路由测试基建**：需要 mock `useNavigate` 或在 `MemoryRouter` 中渲染并读取 URL；ChatPage 已有 `MemoryRouter` 模式可参照，无新增依赖
- **轻量 dropdown 自实现**：不引入 Radix。简单焦点管理代码量约 60 行；后续如需扩展为通用组件可再抽象
- **现有测试影响**：`McpPage.test.tsx` 中约 18 个测试用例需要拆分到新页面。逐项映射后行为一致即可
- **`destructive` 颜色**：DESIGN.md 仅有 `error / error-soft / error-deep`，足够；不引入新色
- **AdminTokenControl 位置**：保持在列表页 header；不上浮到全局 sidebar，避免在详情页占位
