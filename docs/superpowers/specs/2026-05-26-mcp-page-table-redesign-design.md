# MCP 管理页 — 表格化重构与详情子路由

## 目标

将 `/mcp` 从「左卡片列表 + 右卡片详情」的双面板结构改为「shadcn 风格表格 + 独立详情页」，配套面包屑导航与 shadcn 风格表单抽屉。所有视觉与 token 沿用 `frontend/DESIGN.md`，不引入新的颜色 / 字号 / 阴影系统。

不在范围：后端 API 变更、权限模型变更、分页/虚拟滚动 (留 hook，不实现)。

## 路由

新增嵌套路由：

```
/mcp                      → McpListPage     (表格视图)
/mcp/new                  → McpListPage + create drawer 打开
/mcp/:serverId            → McpDetailPage   (详情页，tabs: 配置 | 工具快照)
/mcp/:serverId/edit       → McpDetailPage + edit drawer 打开
```

- `useNavigate()` + `useParams()` 驱动跳转，browser back / refresh 可用。
- `WorkspaceSidebar` 在 `pathname.startsWith('/mcp')` 时 `activeKey="mcp"`。
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
| `+ 新增 Server` (右对齐) | `h-9 rounded-lg bg-primary text-on-primary px-3 text-xs font-medium hover:bg-primary-deep` → `navigate('/mcp/new')` |

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
- `border-b border-hairline last:border-0 hover:bg-canvas-soft transition-colors cursor-pointer`
- 整行 onClick → `navigate('/mcp/' + server.id)`
- `⋯` 按钮 `onClick={(e) => { e.stopPropagation(); ... }}` 避免触发跳转

**StatusBadge 颜色**：
- running → `bg-success/15 text-success-deep` + `bg-success` 点
- stopped → `bg-canvas-soft text-mute` + `bg-mute` 点
- error → `bg-error-soft text-error-deep` + `bg-error` 点
- starting/stopping → `bg-primary/10 text-ink` + `bg-primary` 点
- unknown → `bg-canvas-soft text-mute` + `bg-hairline-strong` 点

### Row action dropdown

自实现轻量 `<Menu>` (无 Radix)：
- `position: absolute` 锚到 trigger，`mt-1 right-0 w-44 rounded-lg border border-hairline bg-canvas shadow-md p-1 text-xs`
- 关闭机制：`Escape`，点击 menu 外，选择条目
- 首项 auto-focus，`ArrowUp/Down` 切换，`Enter` 触发
- 关闭时 trigger 重新获得焦点

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
- Footer：`flex items-center justify-between border-t border-hairline px-3 py-2 text-2xs text-mute font-mono` — 左：`共 N 个服务` (筛选时 `· 显示 M 个`)；右：预留分页区

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
- 右：`编辑` (h-9 ghost) · `删除` (h-9 destructive ghost) · `⋯` 触发与 row 相同的动作 dropdown (Start/Stop/Restart/Check)

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
- 删除成功 → `navigate('/mcp', { replace: true })` + `refetchServers()`
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
- **per-field error** 渲染在字段下方 (新)
- 顶部 `role="alert"` 区域**保留**仅用于来自 API 的非字段错误 (`mutations.error`)
- 测试断言 "请填写服务名称。" 等仍可通过 `getByRole("alert")` 命中 (作为 fallback：若没有字段级别错误，原 alert 行为不变；但实现上字段错误本身也带 `role="alert"`，这是更可访问的做法且不破坏现有测试)

校验规则保留原有：
1. 名称必填
2. stdio → command 必填
3. http → url 必填且必须可 `new URL()` 解析
4. env / headers 每行 `KEY=VALUE` 格式

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
    errorMessages.ts      (沿用)
  hooks.ts                (沿用)
  adminToken.ts           (沿用)
  types.ts                (沿用)
```

`McpPage.tsx` 删除；旧 `McpServerList.tsx` / `McpServerDetail.tsx` 删除。

`AdminTokenControl` 提取为独立小组件复用于列表页 header (从现 `McpPage.tsx` 拆出)。

## 状态管理与数据流

- 列表页：`useMcpServers()` + 本地 `searchText` / `statusFilter`；mutation 走 `useMcpMutations()`，成功后 `refetchServers()`；删除从 row dropdown 触发时如果当前没有详情页打开，直接刷新列表即可
- 详情页：`useParams<{serverId: string}>()` → `useMcpServerDetail(serverId)`；mutation 同上，成功后并行 `refetchServers() + refetchDetail()`
- 404 处理：详情页 `isMcpNotFoundError(detailState.error)` → 渲染「服务不存在」卡片 (而不是 `useEffect` 副作用跳回)；这样 URL 保留，用户主动点 `返回列表`
- 双页共享的 mutation 行为通过 `useMcpMutations()` hook 自然共用，无需提升状态

## 测试策略

保留并扩展。要点：

**`McpListPage.test.tsx`** (替换 `McpPage.test.tsx` 中列表相关用例)：
- 渲染 toolbar / table headers / 行
- 行点击跳转 `/mcp/:id` (`MemoryRouter` + `useLocation` 探针)
- `⋯` 菜单：键盘 (Escape 关闭、ArrowDown/Up、Enter 触发)、点外关闭、stopPropagation 不触发行跳转
- 启动/停止/重启/检查/删除从菜单触发；确认 dialog 与现有断言一致
- 状态筛选 / 搜索过滤
- 空 / 加载 / 错误三态
- footer 计数
- Admin Token 保存与刷新 (沿用现有用例)

**`McpDetailPage.test.tsx`** (新)：
- `/mcp/srv-1` 渲染面包屑两段、H1 名称、StatusBadge
- 切换 tab 同步 `?tab=tools`
- 配置面板渲染所有定义行；env/headers `********` 展示
- 工具表格行 + `查看 schema` 展开 `<pre>`
- 404 → "MCP 服务不存在" + 返回列表按钮
- 删除成功 → `navigate('/mcp')` (mock `useNavigate`)
- 编辑按钮 → 跳 `/mcp/:id/edit`

**`McpRowActionsMenu.test.tsx`** (新)：菜单独立测试。

**`McpServerFormDrawer.test.tsx`** (新或扩展)：
- 每个字段 label 关联输入
- 提交后字段级错误显示在字段下方 (`aria-describedby` 指向错误)
- 第一项错误 auto-focus
- 用户键入清除错误
- 现有 "请填写服务名称。" / "stdio 模式需要填写 command。" / "请填写有效的 http url。" / "env 第 1 行需要使用 KEY=VALUE 格式。" 文案保持不变
- `Escape` 关闭、Tab/Shift+Tab 焦点 wrap 沿用现有用例
- payload 字段 (args/env/headers 解析、redacted ******** 省略) 沿用现有用例

**`McpStatusBadge.test.tsx`** (新)：每种 status 的颜色 class 断言。

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
