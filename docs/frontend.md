# Frontend Architecture And UI Conventions

This document records the current frontend implementation contract. For visual
changes, `DESIGN.md` remains the source of truth; this file explains how the
current React app applies that design system in layout, routing, breadcrumbs,
and MCP management pages.

## Scope

The frontend has two primary workspaces:

- SOP quality check chat workflow.
- MCP server management workflow for administrator operations.

Both workspaces share the same top-level shell. Page implementations should not
create their own global sidebar or independent app frame.

## Stack

- Vite
- React 19
- TypeScript
- React Router
- Tailwind CSS v4 through `@tailwindcss/vite`
- Streamdown for streamed markdown
- Vitest and React Testing Library for frontend tests
- Playwright smoke scripts for browser-level checks

## Visual Direction

The current UI follows the Meta-inspired design tokens in `DESIGN.md`.

Core visual rules:

- Use a bright canvas with a subtle blue aurora background, not a flat gray page.
- Use Meta blue as the primary action color: `#0064e0`, with `#0091ff` and
  `#0457cb` for gradient and pressed states.
- Use `Optimistic Text` / `Optimistic Display` first in the font stack, with
  Chinese and system fallbacks after it.
- Use compact application typography. Tables, status text, form helper text,
  and breadcrumbs should use `text-xs` or `text-sm` unless they are page titles.
- Use large pill buttons for primary actions and rounded cards for content
  surfaces.
- Use `canvas`, `canvas-soft`, `canvas-soft-2`, `hairline`, `hairline-soft`,
  `ink`, `body`, `mute`, `primary`, `primary-soft`, `success`, and `error`
  Tailwind tokens rather than ad-hoc colors.
- Reserve the `tech-primary-button` treatment for high-intent launch/create
  actions such as starting a SOP quality check or adding an MCP server.

Shared CSS lives in `frontend/src/styles/globals.css`. The key global utilities
are:

- `bg-aurora` for the app-level background gradient.
- `tech-primary-button` for the gradient primary CTA.
- Streamdown markdown styling for run output.

## App Shell

`frontend/src/app/App.tsx` owns the global app shell and all page routing.

The shell structure is:

```text
BrowserRouter
  Routes
    / -> WorkspaceFrame
      index -> /sop
      /sop -> ChatPage
      /mcp -> ProtectedRoute -> McpListPage
      /mcp/new -> ProtectedRoute -> McpCreatePage
      /mcp/:serverId/edit -> ProtectedRoute -> McpEditPage
      /mcp/:serverId -> ProtectedRoute -> McpDetailPage
      * -> /sop
```

`WorkspaceFrame` owns:

- sidebar open/collapse state
- active workspace detection from `location.pathname`
- navigation callbacks for SOP and MCP
- recent SOP refresh events
- optional per-page sidebar content through `WorkspaceLayoutContext`

Page components should render only their main content area. They should not wrap
pages in another `BrowserRouter`, duplicate `WorkspaceSidebar`, or own the full
viewport frame.

## Sidebar

The global sidebar is `frontend/src/app/WorkspaceSidebar.tsx` and uses the local
shadcn-style primitives in `frontend/src/components/ui/sidebar.tsx`.

Sidebar rules:

- `发起新SOP质检` is the first navigation item.
- `MCP 管理` sits directly under `发起新SOP质检` in the same navigation group.
- The sidebar supports collapsed and expanded states.
- `RecentSopSidebarPanel` is the default sidebar content and remains available
  across the workspace shell.
- Feature pages may set temporary sidebar content through
  `WorkspaceLayoutContext`, but should clear it on unmount when needed.
- Left sidebar height and right page content height are independent; page bodies
  should own their own scrolling.

## Routing And Authorization

The app bootstraps auth before rendering the workspace. In Vite dev mode, a
401 from `GET /api/auth/me` renders the development user picker for `common`
and `admin`. Selecting a user calls `POST /api/auth/dev-login`, which creates
the `cqa_user` dev session cookie, then the frontend refreshes the current-user
state and enters the app.

MCP routes are protected as a route group in `App.tsx`:

```tsx
<Route element={<ProtectedRoute />}>
  <Route element={<McpListPage />} path="mcp" />
  <Route element={<McpCreatePage />} path="mcp/new" />
  <Route element={<McpEditPage />} path="mcp/:serverId/edit" />
  <Route element={<McpDetailPage />} path="mcp/:serverId" />
</Route>
```

`ProtectedRoute` delegates policy to `useAuthz()`, which reads the authenticated
user from the auth context. Non-admin users can load SOP pages but receive the
MCP route-level 403 state.

Navigation rules:

- `/` redirects to `/sop`.
- Unknown routes redirect to `/sop`.
- Sidebar SOP click navigates to `/sop` or starts a new SOP conversation if the
  SOP page has registered a handler.
- Sidebar MCP click navigates to `/mcp`; clicking it while already in MCP is a
  no-op.
- MCP row names link to `/mcp/:serverId`.
- MCP row actions link to detail/edit routes or call lifecycle APIs.

## Breadcrumbs

MCP pages use `frontend/src/features/mcp/components/McpBreadcrumb.tsx`.

Breadcrumb rules:

- Every MCP page shows breadcrumbs. The list, create, edit, and detail pages
  should be consistent.
- Breadcrumbs render directly on the page background, without an extra divider
  or boxed header treatment.
- The current segment uses `aria-current="page"`.
- Intermediate segments are links, for example `MCP 管理 -> Alpha Server -> 编辑`.
- Long server names should truncate rather than expanding the header.

Current breadcrumb patterns:

| Route | Breadcrumb |
| --- | --- |
| `/mcp` | `MCP 管理` |
| `/mcp/new` | `MCP 管理 / 新增 Server` |
| `/mcp/:serverId` | `MCP 管理 / {server.name}` |
| `/mcp/:serverId/edit` | `MCP 管理 / {server.name} / 编辑` |

## MCP Page Layout

`frontend/src/features/mcp/pages/McpPageLayout.tsx` is the shared layout for MCP
create, edit, and detail pages. The list page follows the same header and scroll
rules directly.

Layout rules:

- `main` uses `flex min-h-0 flex-1 flex-col overflow-hidden`.
- Header uses transparent background and compact spacing, so breadcrumbs and
  titles sit directly on the app background.
- The scrollable body is the page body, not the whole viewport shell:
  `min-h-0 flex-1 overflow-y-auto p-4`.
- Page titles use compact sizing (`text-base` currently) to match the chat page
  density.
- Form and detail content should be grouped into rounded cards using the design
  tokens, not large decorative banners.

## MCP List Table

The MCP list uses a compact operational table/card hybrid in
`McpServerTable.tsx`.

Table rules:

- Toolbar controls are left-aligned: search, status filter, refresh; create CTA
  stays on the right when space allows.
- The table uses meaningful columns instead of synthetic health scores:
  `MCP 服务`, `启用策略`, `连接配置`, `工具`, `运行状态`, `最近检查`, `操作`.
- Server names link to detail pages.
- `command` is intentionally visually smaller than `args`; args carry more
  operational context.
- Runtime errors are shown as operational status, not as oversized red page
  banners.
- Row action menus are portaled to `document.body` to avoid clipping inside
  scrollable table containers.

## MCP Forms And Feedback

MCP create and edit pages are full pages with breadcrumbs, not blank redirects or
drawers.

Form rules:

- Create page route: `/mcp/new`.
- Edit page route: `/mcp/:serverId/edit`.
- Save success navigates to the detail page with a transient success notice in
  route state.
- Detail page displays the success notice with `role="status"`.
- Stdio forms emphasize `args` over `command`, because args carry the actual MCP
  package and root configuration.
- HTTP forms use the configured URL and headers; secrets remain redacted in API
  responses.

## MCP Authorization

The MCP frontend relies on the authenticated `cqa_user` cookie for API calls.
MCP pages and backend MCP APIs are restricted to admin users; there is no
separate MCP credential or custom request header.

## Local MCP HTTP Echo Server

For local streamable HTTP MCP testing, use:

```bash
./.venv/bin/python scripts/mcp_http_echo_server.py --host 127.0.0.1 --port 18000 --path /mcp
```

The server exposes one tool:

- `echo(message: str) -> str`

A configured HTTP MCP server pointed at `http://127.0.0.1:18000/mcp` should pass
`check` and discover the `echo` tool.
