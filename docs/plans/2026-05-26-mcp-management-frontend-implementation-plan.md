# MCP Management Frontend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在前端新增受保护的 `/mcp` 管理页，支持 MCP server 的 CRUD、生命周期操作和工具快照查看。

**Architecture:** 采用 `react-router-dom` 建立 `/sop` 与 `/mcp` 双页面结构，新增 `AppShell` 承载统一侧边导航。MCP 功能按现有 `features/*` 分层新增 `features/mcp`（types/api/hooks/pages/components），并通过 `ProtectedRoute` 与 `useAuthz` 预留管理员访问控制。

**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS v4, Vitest, React Testing Library

---

### Task 1: 接入路由基础设施

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/app/App.tsx`
- Create: `frontend/src/app/AppShell.tsx`

**Step 1: Write the failing test**

Create/modify `frontend/src/app/App.test.tsx` to assert:

```tsx
it("renders sop route by default", async () => {
  window.history.pushState({}, "", "/");
  render(<App />);
  expect(await screen.findByText(/质量检查|SOP/i)).toBeInTheDocument();
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- src/app/App.test.tsx`
Expected: FAIL (router/app shell not implemented).

**Step 3: Write minimal implementation**

1. 安装依赖：`react-router-dom`。
2. 在 `App.tsx` 中挂载 `BrowserRouter + Routes`。
3. 新建 `AppShell.tsx` 只渲染基础 layout 与 `Outlet`。

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- src/app/App.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/app/App.tsx frontend/src/app/AppShell.tsx frontend/src/app/App.test.tsx
git commit -m "feat(frontend): add router shell for sop and mcp pages"
```

### Task 2: 迁移现有 SOP 页面到 `/sop`

**Files:**
- Modify: `frontend/src/features/sop/pages/ChatPage.tsx`
- Modify: `frontend/src/app/App.tsx`
- Test: `frontend/src/features/sop/pages/ChatPage.test.tsx`

**Step 1: Write the failing test**

Add route-level test:

```tsx
it("renders chat page on /sop", async () => {
  window.history.pushState({}, "", "/sop");
  render(<App />);
  expect(await screen.findByRole("form", { name: "SOP 运行表单" })).toBeInTheDocument();
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- src/features/sop/pages/ChatPage.test.tsx`
Expected: FAIL.

**Step 3: Write minimal implementation**

1. 在路由里绑定 `/sop` 到 `ChatPage`。
2. 默认 `*` 重定向到 `/sop`。

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- src/features/sop/pages/ChatPage.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/app/App.tsx frontend/src/features/sop/pages/ChatPage.tsx frontend/src/features/sop/pages/ChatPage.test.tsx
git commit -m "refactor(frontend): mount sop page on /sop route"
```

### Task 3: 新增 `/mcp` 路由保护骨架

**Files:**
- Create: `frontend/src/app/routing/ProtectedRoute.tsx`
- Create: `frontend/src/app/routing/useAuthz.ts`
- Create: `frontend/src/app/routing/ProtectedRoute.test.tsx`
- Modify: `frontend/src/app/App.tsx`

**Step 1: Write the failing test**

```tsx
it("blocks non-admin route access", () => {
  // mock useAuthz => { isAdmin: false }
  // visit /mcp
  // expect 403 placeholder text
});
```

```tsx
it("allows admin route access", () => {
  // mock useAuthz => { isAdmin: true }
  // visit /mcp
  // expect MCP page heading visible
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- src/app/routing/ProtectedRoute.test.tsx`
Expected: FAIL.

**Step 3: Write minimal implementation**

1. `useAuthz` 返回 `{ isAdmin: true }`（占位实现）。
2. `ProtectedRoute` 根据 `isAdmin` 返回 `Outlet` 或 403 占位。
3. `/mcp` 路由使用 `ProtectedRoute` 包裹。

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- src/app/routing/ProtectedRoute.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/app/App.tsx frontend/src/app/routing/useAuthz.ts frontend/src/app/routing/ProtectedRoute.tsx frontend/src/app/routing/ProtectedRoute.test.tsx
git commit -m "feat(frontend): add protected route scaffold for mcp page"
```

### Task 4: 搭建 MCP 类型与 API 客户端

**Files:**
- Create: `frontend/src/features/mcp/types.ts`
- Create: `frontend/src/features/mcp/api.ts`
- Create: `frontend/src/features/mcp/api.test.ts`

**Step 1: Write the failing test**

覆盖：
1. list/get/create/update/delete 请求路径与 method。
2. lifecycle 请求路径（start/stop/restart/check）。
3. 409/404/502 错误透传 `ApiError.detail`。

示例：

```ts
it("calls lifecycle start endpoint", async () => {
  // mock fetch 200
  await startMcpServer("id-1");
  expect(fetch).toHaveBeenCalledWith(
    "/api/mcp/servers/id-1/start",
    expect.objectContaining({ method: "POST" }),
  );
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- src/features/mcp/api.test.ts`
Expected: FAIL.

**Step 3: Write minimal implementation**

在 `api.ts` 添加：
1. `listMcpServers`
2. `getMcpServer`
3. `createMcpServer`
4. `updateMcpServer`
5. `deleteMcpServer`
6. `startMcpServer`
7. `stopMcpServer`
8. `restartMcpServer`
9. `checkMcpServer`

全部复用 `requestJson`。

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- src/features/mcp/api.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/features/mcp/types.ts frontend/src/features/mcp/api.ts frontend/src/features/mcp/api.test.ts
git commit -m "feat(frontend): add mcp api client and schema types"
```

### Task 5: 实现 MCP hooks 与页面状态编排

**Files:**
- Create: `frontend/src/features/mcp/hooks.ts`
- Create: `frontend/src/features/mcp/hooks.test.tsx`

**Step 1: Write the failing test**

覆盖：
1. 首次加载列表。
2. 触发 mutation 后刷新列表。
3. 选中项详情刷新。

示例：

```tsx
it("refreshes list after start action", async () => {
  // render hook
  // call start action
  // expect list refetch called
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- src/features/mcp/hooks.test.tsx`
Expected: FAIL.

**Step 3: Write minimal implementation**

实现：
1. `useMcpServers`（loading/error/data/refetch）
2. `useMcpServerDetail`（selected id 驱动）
3. `useMcpMutations`（统一 pending/error/success 回调）

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- src/features/mcp/hooks.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/features/mcp/hooks.ts frontend/src/features/mcp/hooks.test.tsx
git commit -m "feat(frontend): add mcp data hooks and mutation flow"
```

### Task 6: 实现 MCP 页面布局（列表 + 详情 + Tabs）

**Files:**
- Create: `frontend/src/features/mcp/pages/McpPage.tsx`
- Create: `frontend/src/features/mcp/components/McpServerList.tsx`
- Create: `frontend/src/features/mcp/components/McpServerDetail.tsx`
- Create: `frontend/src/features/mcp/components/McpServerFormDrawer.tsx`
- Create: `frontend/src/features/mcp/pages/McpPage.test.tsx`
- Modify: `frontend/src/app/AppShell.tsx`
- Modify: `frontend/src/styles/globals.css` (if needed for tokens/utilities)

**Step 1: Write the failing test**

覆盖：
1. 左栏渲染 server 列表。
2. 点击列表项切换右栏详情。
3. tab 切换到 tools snapshot 可见工具。
4. 触发 `start/stop/restart/check` 调用对应 action。

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- src/features/mcp/pages/McpPage.test.tsx`
Expected: FAIL.

**Step 3: Write minimal implementation**

1. 主布局实现两栏与顶部操作。
2. 左栏实现搜索/筛选/列表/快捷操作。
3. 右栏实现状态卡片 + config/tools tabs。
4. 抽屉实现新增与编辑。
5. 侧边导航增加 `/mcp` 入口。

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- src/features/mcp/pages/McpPage.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/features/mcp frontend/src/app/AppShell.tsx frontend/src/styles/globals.css
git commit -m "feat(frontend): build mcp management workspace page"
```

### Task 7: 错误处理与交互完善

**Files:**
- Modify: `frontend/src/features/mcp/pages/McpPage.tsx`
- Modify: `frontend/src/features/mcp/components/*`
- Test: `frontend/src/features/mcp/pages/McpPage.test.tsx`

**Step 1: Write the failing test**

新增断言：
1. `409` 显示“请先停止服务再修改配置”。
2. 删除/重启触发二次确认。
3. `404` 时清空选中项。

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- src/features/mcp/pages/McpPage.test.tsx`
Expected: FAIL.

**Step 3: Write minimal implementation**

1. 错误码映射到清晰中文提示。
2. 二次确认弹窗。
3. 404 自动回收选中状态。

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- src/features/mcp/pages/McpPage.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/features/mcp
git commit -m "feat(frontend): improve mcp error handling and safeguards"
```

### Task 8: 全量回归与文档同步

**Files:**
- Modify: `frontend/README.md`
- Modify: `docs/frontend.md`
- Optional: `api/openapi.yml` (only if frontend发现契约不一致并需修正文档)

**Step 1: Run focused tests**

Run:

```bash
cd frontend
npm test -- src/app src/features/mcp src/features/sop/pages/ChatPage.test.tsx
```

Expected: PASS.

**Step 2: Run full frontend test suite**

Run: `cd frontend && npm test`
Expected: PASS.

**Step 3: Update docs**

1. 在 `frontend/README.md` 记录新路由 `/mcp`。
2. 在 `docs/frontend.md` 更新页面结构与职责。

**Step 4: Commit**

```bash
git add frontend/README.md docs/frontend.md
git commit -m "docs(frontend): document mcp management route and architecture"
```

### Task 9: 最终质量门禁

**Files:**
- No code changes expected (unless failing checks require fixes)

**Step 1: Verify lint/type/test**

Run:

```bash
cd frontend
npm run lint || true
npm run typecheck || true
npm test
```

Expected: 测试通过；若 lint/typecheck 脚本不存在，记录为风险并在 PR 描述说明。

**Step 2: Git check**

Run:

```bash
git status --short
```

Expected: 工作区干净。

**Step 3: Final commit (only if fixes were needed)**

```bash
git add <changed-files>
git commit -m "chore(frontend): final polish for mcp management page"
```
