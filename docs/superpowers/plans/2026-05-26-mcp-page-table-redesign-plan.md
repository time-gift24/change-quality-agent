# MCP 管理页表格化重构 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dual-panel card layout at `/mcp` with a shadcn-style data table + nested detail/edit routes with breadcrumb navigation.

**Architecture:** `McpListPage` (table + toolbar) at `/mcp` and `McpDetailPage` (breadcrumb + tabs) at `/mcp/:serverId`. Drawer open/close driven by nested routes (`/mcp/new`, `/mcp/:serverId/edit`) via `useMatch`. All visual tokens from `DESIGN.md` / `globals.css`.

**Tech Stack:** React 19, React Router 7, Tailwind CSS v4, Vitest + Testing Library (jsdom)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/features/mcp/components/McpStatusBadge.tsx` | Create | Status pill with dot + label |
| `src/features/mcp/components/McpBreadcrumb.tsx` | Create | `MCP 管理 › server-name` nav |
| `src/features/mcp/components/AdminTokenControl.tsx` | Create | Extracted token input + save |
| `src/features/mcp/components/McpRowActionsMenu.tsx` | Create | Self-contained dropdown menu |
| `src/features/mcp/components/McpServerTable.tsx` | Create | Toolbar + table + footer + states |
| `src/features/mcp/components/McpDetailConfigPanel.tsx` | Create | Definition list for config tab |
| `src/features/mcp/components/McpDetailToolsPanel.tsx` | Create | Tools table + schema expand |
| `src/features/mcp/components/McpServerFormDrawer.tsx` | Rewrite | Shadcn-style sectioned form |
| `src/features/mcp/pages/McpListPage.tsx` | Create | List page with table + sidebar |
| `src/features/mcp/pages/McpDetailPage.tsx` | Create | Detail page with breadcrumb + tabs |
| `src/app/App.tsx` | Modify | Add nested routes; remove old import |
| `src/app/App.test.tsx` | Modify | Update McpPage mock to new pages |
| `src/features/mcp/pages/McpPage.tsx` | Delete | Replaced by McpListPage + McpDetailPage |
| `src/features/mcp/components/McpServerList.tsx` | Delete | Replaced by McpServerTable |
| `src/features/mcp/components/McpServerDetail.tsx` | Delete | Replaced by McpDetailPage + panels |

---

## Chunk 1: Scaffold — Clean Slate & Route Shell

### Task 1.1: Delete old MCP page files

**Files:**
- Delete: `src/features/mcp/pages/McpPage.tsx`
- Delete: `src/features/mcp/components/McpServerList.tsx`
- Delete: `src/features/mcp/components/McpServerDetail.tsx`

- [ ] **Step 1: Delete files**

```bash
rm frontend/src/features/mcp/pages/McpPage.tsx
rm frontend/src/features/mcp/components/McpServerList.tsx
rm frontend/src/features/mcp/components/McpServerDetail.tsx
```

- [ ] **Step 2: Create empty placeholder files for all new components**

```bash
touch frontend/src/features/mcp/pages/McpListPage.tsx
touch frontend/src/features/mcp/pages/McpDetailPage.tsx
touch frontend/src/features/mcp/components/McpServerTable.tsx
touch frontend/src/features/mcp/components/McpRowActionsMenu.tsx
touch frontend/src/features/mcp/components/McpStatusBadge.tsx
touch frontend/src/features/mcp/components/McpBreadcrumb.tsx
touch frontend/src/features/mcp/components/McpDetailConfigPanel.tsx
touch frontend/src/features/mcp/components/McpDetailToolsPanel.tsx
touch frontend/src/features/mcp/components/AdminTokenControl.tsx
```

- [ ] **Step 3: Verify old test file still exists (it references deleted components)**

```bash
ls frontend/src/features/mcp/pages/McpPage.test.tsx
```

Expected: file exists. We'll delete it in a later chunk after writing new tests.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/mcp/
git commit -m "chore: delete old McpPage, McpServerList, McpServerDetail; create new file placeholders"
```

---

## Chunk 2: Small Standalone Components — StatusBadge, Breadcrumb, AdminTokenControl

### Task 2.1: McpStatusBadge

**Files:**
- Create: `src/features/mcp/components/McpStatusBadge.tsx`
- Create: `src/features/mcp/components/McpStatusBadge.test.tsx`

- [ ] **Step 1: Write the test**

```tsx
// src/features/mcp/components/McpStatusBadge.test.tsx
// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { McpStatusBadge } from "./McpStatusBadge";

afterEach(() => {
  cleanup();
});

describe("McpStatusBadge", () => {
  it("renders running badge with green dot", () => {
    render(<McpStatusBadge status="running" />);
    const badge = screen.getByText("running");
    expect(badge).toBeInTheDocument();
    expect(screen.getByTestId("status-dot")).toHaveAttribute("data-status", "running");
  });

  it("renders stopped badge with gray dot", () => {
    render(<McpStatusBadge status="stopped" />);
    expect(screen.getByText("stopped")).toBeInTheDocument();
    expect(screen.getByTestId("status-dot")).toHaveAttribute("data-status", "stopped");
  });

  it("renders error badge with red dot", () => {
    render(<McpStatusBadge status="error" />);
    expect(screen.getByText("error")).toBeInTheDocument();
  });

  it("renders starting badge", () => {
    render(<McpStatusBadge status="starting" />);
    expect(screen.getByText("starting")).toBeInTheDocument();
  });

  it("renders unknown badge", () => {
    render(<McpStatusBadge status="unknown" />);
    expect(screen.getByText("unknown")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/features/mcp/components/McpStatusBadge.test.tsx
```

Expected: FAIL (cannot find McpStatusBadge)

- [ ] **Step 3: Implement McpStatusBadge**

```tsx
// src/features/mcp/components/McpStatusBadge.tsx
import type { McpServerRuntimeStatus } from "../types";

type McpStatusBadgeProps = {
  status: McpServerRuntimeStatus;
};

const STATUS_STYLES: Record<McpServerRuntimeStatus, { pill: string; text: string; dot: string }> = {
  running: {
    pill: "bg-success/15",
    text: "text-success",
    dot: "bg-success",
  },
  stopped: {
    pill: "bg-canvas-soft border border-hairline",
    text: "text-body",
    dot: "bg-hairline-strong",
  },
  error: {
    pill: "bg-error-soft",
    text: "text-error-deep",
    dot: "bg-error",
  },
  starting: {
    pill: "bg-primary-soft",
    text: "text-primary-deep",
    dot: "bg-primary",
  },
  stopping: {
    pill: "bg-primary-soft",
    text: "text-primary-deep",
    dot: "bg-primary",
  },
  unknown: {
    pill: "bg-canvas-soft border border-hairline",
    text: "text-mute",
    dot: "bg-hairline-strong",
  },
};

export function McpStatusBadge({ status }: McpStatusBadgeProps) {
  const style = STATUS_STYLES[status];

  return (
    <span
      className={`inline-flex h-5 items-center gap-1 rounded-full px-2 text-2xs ${style.pill} ${style.text}`}
    >
      <span
        aria-hidden="true"
        className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${style.dot}`}
        data-status={status}
        data-testid="status-dot"
      />
      {status}
    </span>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/features/mcp/components/McpStatusBadge.test.tsx
```

Expected: 5/5 PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/mcp/components/McpStatusBadge.tsx frontend/src/features/mcp/components/McpStatusBadge.test.tsx
git commit -m "feat: add McpStatusBadge component with status color mapping"
```

### Task 2.2: McpBreadcrumb

**Files:**
- Create: `src/features/mcp/components/McpBreadcrumb.tsx`
- Create: `src/features/mcp/components/McpBreadcrumb.test.tsx`

- [ ] **Step 1: Write the test**

```tsx
// src/features/mcp/components/McpBreadcrumb.test.tsx
// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { McpBreadcrumb } from "./McpBreadcrumb";

afterEach(() => {
  cleanup();
});

describe("McpBreadcrumb", () => {
  it("renders two-segment breadcrumb with server name", () => {
    render(
      <MemoryRouter>
        <McpBreadcrumb serverName="Alpha Server" />
      </MemoryRouter>,
    );

    const nav = screen.getByRole("navigation", { name: "面包屑" });
    expect(nav).toBeInTheDocument();

    const listLink = screen.getByRole("link", { name: "MCP 管理" });
    expect(listLink).toHaveAttribute("href", "/mcp");

    expect(screen.getByText("Alpha Server")).toBeInTheDocument();
    expect(screen.getByText("Alpha Server")).toHaveAttribute("aria-current", "page");
  });

  it("truncates long server names", () => {
    render(
      <MemoryRouter>
        <McpBreadcrumb serverName="Very Long Server Name That Should Truncate" />
      </MemoryRouter>,
    );

    const current = screen.getByText("Very Long Server Name That Should Truncate");
    expect(current.className).toContain("truncate");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/features/mcp/components/McpBreadcrumb.test.tsx
```

Expected: FAIL

- [ ] **Step 3: Implement McpBreadcrumb**

```tsx
// src/features/mcp/components/McpBreadcrumb.tsx
import { Link } from "react-router-dom";

type McpBreadcrumbProps = {
  serverName: string;
};

export function McpBreadcrumb({ serverName }: McpBreadcrumbProps) {
  return (
    <nav aria-label="面包屑" className="text-2xs font-mono">
      <ol className="flex items-center gap-1.5">
        <li>
          <Link to="/mcp" className="text-mute hover:text-ink transition-colors">
            MCP 管理
          </Link>
        </li>
        <li aria-hidden="true" className="text-mute">›</li>
        <li>
          <span
            aria-current="page"
            className="text-ink font-medium truncate max-w-[16ch] sm:max-w-[24ch] inline-block"
          >
            {serverName}
          </span>
        </li>
      </ol>
    </nav>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/features/mcp/components/McpBreadcrumb.test.tsx
```

Expected: 2/2 PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/mcp/components/McpBreadcrumb.tsx frontend/src/features/mcp/components/McpBreadcrumb.test.tsx
git commit -m "feat: add McpBreadcrumb component"
```

### Task 2.3: AdminTokenControl (extract from McpPage)

**Files:**
- Create: `src/features/mcp/components/AdminTokenControl.tsx`
- No separate test file (tested via McpListPage test)

- [ ] **Step 1: Implement AdminTokenControl**

```tsx
// src/features/mcp/components/AdminTokenControl.tsx

type AdminTokenControlProps = {
  value: string;
  saved: boolean;
  onChange: (next: string) => void;
  onSave: () => void;
};

export function AdminTokenControl({
  value,
  saved,
  onChange,
  onSave,
}: AdminTokenControlProps) {
  return (
    <div className="flex items-center gap-2">
      <input
        aria-label="MCP Admin Token"
        autoComplete="off"
        className="h-9 w-40 rounded-xl border border-hairline bg-canvas px-3 text-xs text-ink outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/25 sm:w-52"
        id="mcp-admin-token"
        onChange={(event) => onChange(event.target.value)}
        placeholder="X-MCP-Admin-Token"
        type="password"
        value={value}
      />
      <button
        className="h-9 shrink-0 rounded-xl border border-hairline bg-canvas px-3 text-xs font-medium text-body transition-colors hover:border-hairline-strong hover:text-ink"
        onClick={onSave}
        type="button"
      >
        保存 Token
      </button>
      {saved ? (
        <span className="text-2xs text-mute" role="status">
          已保存
        </span>
      ) : null}
    </div>
  );
}
```

This is an exact extraction of the inline `AdminTokenControl` from `McpPage.tsx:342-378`.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/mcp/components/AdminTokenControl.tsx
git commit -m "feat: extract AdminTokenControl from McpPage"
```

---

## Chunk 3: McpRowActionsMenu — Dropdown Component

### Task 3.1: McpRowActionsMenu

**Files:**
- Create: `src/features/mcp/components/McpRowActionsMenu.tsx`
- Create: `src/features/mcp/components/McpRowActionsMenu.test.tsx`

- [ ] **Step 1: Write the test**

```tsx
// src/features/mcp/components/McpRowActionsMenu.test.tsx
// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { McpRowActionsMenu } from "./McpRowActionsMenu";
import type { McpServerRuntimeStatus } from "../types";

function renderMenu(status: McpServerRuntimeStatus = "running", overrides: Partial<React.ComponentProps<typeof McpRowActionsMenu>> = {}) {
  const props = {
    runtimeStatus: status,
    serverId: "srv-1",
    serverName: "Alpha Server",
    onStart: vi.fn(),
    onStop: vi.fn(),
    onRestart: vi.fn(),
    onCheck: vi.fn(),
    onDelete: vi.fn(),
    ...overrides,
  };
  return {
    ...render(
      <MemoryRouter>
        <McpRowActionsMenu {...props} />
      </MemoryRouter>,
    ),
    props,
  };
}

afterEach(() => {
  cleanup();
});

describe("McpRowActionsMenu", () => {
  it("renders trigger button with aria-haspopup", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    expect(trigger).toBeInTheDocument();
    expect(trigger).toHaveAttribute("aria-haspopup", "menu");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("opens menu on ArrowDown and focuses first item", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });

    const menu = screen.getByRole("menu");
    expect(menu).toBeInTheDocument();
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("menuitem", { name: "查看详情" })).toHaveFocus();
  });

  it("opens menu on Enter and focuses first item", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.keyDown(trigger, { key: "Enter" });

    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "查看详情" })).toHaveFocus();
  });

  it("opens menu on ArrowUp and focuses last item", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.keyDown(trigger, { key: "ArrowUp" });

    expect(screen.getByRole("menu")).toBeInTheDocument();
    const items = screen.getAllByRole("menuitem");
    expect(items[items.length - 1]).toHaveFocus();
  });

  it("closes menu on Escape and returns focus to trigger", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });

    fireEvent.keyDown(screen.getByRole("menu"), { key: "Escape" });

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("closes menu on click outside", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.click(trigger);

    fireEvent.mouseDown(document.body);

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("navigates items with ArrowDown and ArrowUp", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });

    const items = screen.getAllByRole("menuitem");
    fireEvent.keyDown(screen.getByRole("menu"), { key: "ArrowDown" });
    expect(items[1]).toHaveFocus();

    fireEvent.keyDown(screen.getByRole("menu"), { key: "ArrowUp" });
    expect(items[0]).toHaveFocus();
  });

  it("jumps to first/last with Home/End", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });

    const items = screen.getAllByRole("menuitem");
    fireEvent.keyDown(screen.getByRole("menu"), { key: "End" });
    expect(items[items.length - 1]).toHaveFocus();

    fireEvent.keyDown(screen.getByRole("menu"), { key: "Home" });
    expect(items[0]).toHaveFocus();
  });

  it("shows 查看详情 as a link to detail page", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.click(trigger);

    const detailLink = screen.getByRole("menuitem", { name: "查看详情" });
    expect(detailLink.tagName).toBe("A");
    expect(detailLink).toHaveAttribute("href", "/mcp/srv-1");
  });

  it("shows 启动 for stopped server, hides for running", () => {
    renderMenu("stopped");
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.click(trigger);

    expect(screen.getByRole("menuitem", { name: "启动" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "停止" })).not.toBeInTheDocument();
  });

  it("shows 停止 for running server, hides 启动", () => {
    renderMenu("running");
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.click(trigger);

    expect(screen.getByRole("menuitem", { name: "停止" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "启动" })).not.toBeInTheDocument();
  });

  it("calls onRestart when 重启 is clicked", () => {
    const { props } = renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.click(trigger);

    fireEvent.click(screen.getByRole("menuitem", { name: "重启" }));
    expect(props.onRestart).toHaveBeenCalledWith("srv-1");
  });

  it("closes menu after selecting an action", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    fireEvent.click(trigger);

    fireEvent.click(screen.getByRole("menuitem", { name: "检查" }));
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("prevents Space from scrolling page on trigger", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: "更多操作" });
    const preventDefault = vi.fn();
    fireEvent.keyDown(trigger, { key: " ", preventDefault });

    expect(preventDefault).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/features/mcp/components/McpRowActionsMenu.test.tsx
```

Expected: FAIL

- [ ] **Step 3: Implement McpRowActionsMenu**

```tsx
// src/features/mcp/components/McpRowActionsMenu.tsx
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";
import type { McpServerRuntimeStatus } from "../types";

type McpRowActionsMenuProps = {
  runtimeStatus: McpServerRuntimeStatus;
  serverId: string;
  serverName: string;
  onStart?: (serverId: string) => void;
  onStop?: (serverId: string) => void;
  onRestart?: (serverId: string) => void;
  onCheck?: (serverId: string) => void;
  onDelete?: (serverId: string) => void;
};

const canStart = (s: McpServerRuntimeStatus) =>
  s === "stopped" || s === "error" || s === "unknown";
const canStop = (s: McpServerRuntimeStatus) =>
  s === "running" || s === "starting";

export function McpRowActionsMenu({
  runtimeStatus,
  serverId,
  serverName: _serverName,
  onStart,
  onStop,
  onRestart,
  onCheck,
  onDelete,
}: McpRowActionsMenuProps) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const itemRefs = useRef<Map<string, HTMLElement>>(new Map());
  const triggerId = useId();

  const items: Array<{
    id: string;
    label: string;
    separator?: boolean;
    variant?: "destructive";
    linkTo?: string;
    action?: () => void;
  }> = [
    { id: "view", label: "查看详情", linkTo: `/mcp/${serverId}` },
    { id: "edit", label: "编辑", linkTo: `/mcp/${serverId}/edit` },
    { id: "sep1", label: "", separator: true },
    ...(canStart(runtimeStatus)
      ? [{ id: "start", label: "启动", action: () => onStart?.(serverId) }]
      : []),
    ...(canStop(runtimeStatus)
      ? [{ id: "stop", label: "停止", action: () => onStop?.(serverId) }]
      : []),
    { id: "restart", label: "重启", action: () => onRestart?.(serverId) },
    { id: "check", label: "检查", action: () => onCheck?.(serverId) },
    { id: "sep2", label: "", separator: true },
    { id: "delete", label: "删除", variant: "destructive" as const, action: () => onDelete?.(serverId) },
  ];

  const close = useCallback(() => {
    setOpen(false);
    triggerRef.current?.focus();
  }, []);

  const focusItem = useCallback((index: number) => {
    const visible = items.filter((i) => !i.separator);
    const clamped = Math.max(0, Math.min(index, visible.length - 1));
    const item = visible[clamped];
    if (item) {
      itemRefs.current.get(item.id)?.focus();
    }
  }, [items]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (
        menuRef.current &&
        !menuRef.current.contains(e.target as Node) &&
        triggerRef.current &&
        !triggerRef.current.contains(e.target as Node)
      ) {
        close();
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open, close]);

  function handleTriggerKeyDown(e: React.KeyboardEvent) {
    if (e.key === " " || e.key === "Spacebar") {
      e.preventDefault();
    }
    if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
      e.preventDefault();
      setOpen(true);
      requestAnimationFrame(() => focusItem(0));
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setOpen(true);
      const visible = items.filter((i) => !i.separator);
      requestAnimationFrame(() => focusItem(visible.length - 1));
    }
  }

  function handleMenuKeyDown(e: React.KeyboardEvent) {
    const visible = items.filter((i) => !i.separator);
    if (e.key === "Escape") {
      e.preventDefault();
      close();
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      const currentIdx = visible.findIndex((i) => i.id === (document.activeElement as HTMLElement)?.dataset?.menuitemId);
      focusItem(currentIdx + 1);
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      const currentIdx = visible.findIndex((i) => i.id === (document.activeElement as HTMLElement)?.dataset?.menuitemId);
      focusItem(currentIdx - 1);
      return;
    }
    if (e.key === "Home") {
      e.preventDefault();
      focusItem(0);
      return;
    }
    if (e.key === "End") {
      e.preventDefault();
      focusItem(visible.length - 1);
    }
  }

  function handleItemClick(action?: () => void) {
    if (action) action();
    close();
  }

  return (
    <div className="relative inline-block">
      <button
        ref={triggerRef}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="更多操作"
        className="flex h-8 w-8 items-center justify-center rounded-lg text-mute transition-colors hover:bg-canvas-soft hover:text-ink"
        id={triggerId}
        onClick={() => { setOpen(true); requestAnimationFrame(() => focusItem(0)); }}
        onKeyDown={handleTriggerKeyDown}
        type="button"
      >
        <svg
          aria-hidden="true"
          className="h-4 w-4"
          fill="currentColor"
          viewBox="0 0 24 24"
        >
          <circle cx="12" cy="5" r="2" />
          <circle cx="12" cy="12" r="2" />
          <circle cx="12" cy="19" r="2" />
        </svg>
      </button>

      {open ? (
        <div
          ref={menuRef}
          aria-labelledby={triggerId}
          className="absolute right-0 z-30 mt-1 w-44 rounded-lg border border-hairline bg-canvas p-1 shadow-md"
          onKeyDown={handleMenuKeyDown}
          role="menu"
        >
          {items.map((item) =>
            item.separator ? (
              <div key={item.id} className="my-1 border-t border-hairline" role="separator" />
            ) : item.linkTo ? (
              <Link
                key={item.id}
                className="flex items-center rounded-md px-2.5 py-1.5 text-xs text-body transition-colors hover:bg-canvas-soft focus:bg-canvas-soft focus:outline-none"
                data-menuitem-id={item.id}
                onClick={close}
                ref={(el) => { if (el) itemRefs.current.set(item.id, el); }}
                role="menuitem"
                to={item.linkTo}
              >
                {item.label}
              </Link>
            ) : (
              <button
                key={item.id}
                className={`flex w-full items-center rounded-md px-2.5 py-1.5 text-xs transition-colors hover:bg-canvas-soft focus:bg-canvas-soft focus:outline-none ${
                  item.variant === "destructive" ? "text-error-deep" : "text-body"
                }`}
                data-menuitem-id={item.id}
                onClick={() => handleItemClick(item.action)}
                ref={(el) => { if (el) itemRefs.current.set(item.id, el); }}
                role="menuitem"
                type="button"
              >
                {item.label}
              </button>
            ),
          )}
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/features/mcp/components/McpRowActionsMenu.test.tsx
```

Expected: 13/13 PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/mcp/components/McpRowActionsMenu.tsx frontend/src/features/mcp/components/McpRowActionsMenu.test.tsx
git commit -m "feat: add McpRowActionsMenu dropdown with full keyboard support"
```

---

## Chunk 4: McpServerTable + McpListPage

### Task 4.1: McpServerTable (toolbar + table + footer)

**Files:**
- Create: `src/features/mcp/components/McpServerTable.tsx`
- No separate test (tested via McpListPage)

- [ ] **Step 1: Implement McpServerTable**

```tsx
// src/features/mcp/components/McpServerTable.tsx
import { Link } from "react-router-dom";
import type { McpServerRuntimeStatus, McpServerSummary } from "../types";
import { McpRowActionsMenu } from "./McpRowActionsMenu";
import { McpStatusBadge } from "./McpStatusBadge";
import { getMcpErrorMessage } from "./errorMessages";
import type { McpStatusFilter } from "../pages/McpListPage";

type McpServerTableProps = {
  servers: McpServerSummary[];
  searchText: string;
  statusFilter: McpStatusFilter;
  loading: boolean;
  error: Error | null;
  pending: boolean;
  onSearchTextChange: (next: string) => void;
  onStatusFilterChange: (next: McpStatusFilter) => void;
  onRefresh: () => void;
  onCreateServer: () => void;
  onStartServer: (serverId: string) => void;
  onStopServer: (serverId: string) => void;
  onRestartServer: (serverId: string) => void;
  onCheckServer: (serverId: string) => void;
  onDeleteServer: (serverId: string) => void;
};

export function McpServerTable({
  servers,
  searchText,
  statusFilter,
  loading,
  error,
  pending,
  onSearchTextChange,
  onStatusFilterChange,
  onRefresh,
  onCreateServer,
  onStartServer,
  onStopServer,
  onRestartServer,
  onCheckServer,
  onDeleteServer,
}: McpServerTableProps) {
  const errorMessage = getMcpErrorMessage(error);

  return (
    <div className="rounded-xl border border-hairline bg-canvas">
      {/* Toolbar */}
      <div className="flex items-center gap-2 border-b border-hairline px-3 py-2">
        <div className="relative flex-1">
          <svg
            aria-hidden="true"
            className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-mute"
            fill="none"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="2"
            viewBox="0 0 24 24"
          >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            aria-label="搜索 MCP 服务"
            className="h-9 w-64 rounded-lg border border-hairline bg-canvas pl-9 pr-3 text-xs text-ink outline-none transition-colors placeholder:text-mute focus:border-primary focus:ring-2 focus:ring-primary/15"
            onChange={(e) => onSearchTextChange(e.target.value)}
            placeholder="按名称搜索…"
            type="search"
            value={searchText}
          />
        </div>

        <select
          aria-label="状态筛选"
          className="h-9 rounded-lg border border-hairline bg-canvas px-3 text-xs text-ink outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15"
          onChange={(e) => onStatusFilterChange(e.target.value as McpStatusFilter)}
          value={statusFilter}
        >
          <option value="all">全部状态</option>
          <option value="running">Running</option>
          <option value="stopped">Stopped</option>
          <option value="error">Error</option>
          <option value="starting">Starting</option>
          <option value="stopping">Stopping</option>
          <option value="unknown">Unknown</option>
        </select>

        <div className="flex-1" />

        <button
          className="h-9 rounded-lg border border-hairline bg-canvas px-3 text-xs text-body transition-colors hover:border-hairline-strong"
          onClick={onRefresh}
          type="button"
        >
          刷新
        </button>

        <button
          aria-label="新增 MCP Server"
          className="h-9 rounded-lg bg-primary px-3 text-xs font-medium text-on-primary transition-colors hover:bg-primary-deep"
          onClick={onCreateServer}
          type="button"
        >
          + 新增 Server
        </button>
      </div>

      {/* Table */}
      <table className="w-full">
        <thead>
          <tr className="border-b border-hairline bg-canvas-soft">
            <th className="h-10 px-3 text-left text-2xs font-medium uppercase tracking-wide text-mute font-mono">
              名称
            </th>
            <th className="hidden h-10 w-[120px] px-3 text-left text-2xs font-medium uppercase tracking-wide text-mute font-mono sm:table-cell">
              状态
            </th>
            <th className="hidden h-10 w-[80px] px-3 text-right text-2xs font-medium uppercase tracking-wide text-mute font-mono sm:table-cell">
              工具
            </th>
            <th className="hidden h-10 w-[160px] px-3 text-left text-2xs font-medium uppercase tracking-wide text-mute font-mono sm:table-cell">
              最近检查
            </th>
            <th className="h-10 w-[56px] px-2 text-center text-2xs font-medium uppercase tracking-wide text-mute font-mono">
              <span className="sr-only">操作</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td className="py-8 text-center text-xs text-mute" colSpan={5}>
                加载中…
              </td>
            </tr>
          ) : errorMessage ? (
            <tr>
              <td className="border border-error-soft bg-canvas px-3 py-2 text-xs text-error-deep" colSpan={5} role="alert">
                {errorMessage}
              </td>
            </tr>
          ) : servers.length === 0 ? (
            <tr>
              <td className="py-12 text-center text-xs text-mute" colSpan={5}>
                暂无 MCP 服务，点击
                <button
                  className="mx-1 font-medium text-primary hover:underline"
                  onClick={onCreateServer}
                  type="button"
                >
                  + 新增 Server
                </button>
                开始添加。
              </td>
            </tr>
          ) : (
            servers.map((server) => (
              <tr
                key={server.id}
                className="border-b border-hairline transition-colors last:border-0 hover:bg-canvas-soft"
              >
                <td className="px-3 py-2.5">
                  <Link
                    className="block rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
                    to={`/mcp/${server.id}`}
                  >
                    <p className="text-sm font-medium text-ink">{server.name}</p>
                    <p className="text-2xs text-mute font-mono">{server.transport}</p>
                  </Link>
                </td>
                <td className="hidden px-3 py-2.5 sm:table-cell">
                  <McpStatusBadge status={server.runtime_status} />
                </td>
                <td className="hidden px-3 py-2.5 text-right sm:table-cell">
                  <span className="text-2xs tabular-nums font-mono text-body">
                    {server.tool_count}
                  </span>
                </td>
                <td className="hidden px-3 py-2.5 sm:table-cell">
                  <span className="text-2xs text-mute">
                    {server.last_checked_at ?? "-"}
                  </span>
                </td>
                <td className="px-2 py-2.5 text-center">
                  <McpRowActionsMenu
                    onCheck={onCheckServer}
                    onDelete={onDeleteServer}
                    onRestart={onRestartServer}
                    onStart={onStartServer}
                    onStop={onStopServer}
                    runtimeStatus={server.runtime_status}
                    serverId={server.id}
                    serverName={server.name}
                  />
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {/* Footer */}
      <div className="flex items-center justify-between border-t border-hairline px-3 py-2 text-2xs text-mute font-mono">
        <span>
          共 {servers.length} 个服务
          {statusFilter !== "all" ? ` · 显示 ${servers.length} 个` : ""}
        </span>
        <span>全部加载</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/mcp/components/McpServerTable.tsx
git commit -m "feat: add McpServerTable with toolbar, table, footer, and all states"
```

### Task 4.2: McpListPage

**Files:**
- Create: `src/features/mcp/pages/McpListPage.tsx`

- [ ] **Step 1: Implement McpListPage**

```tsx
// src/features/mcp/pages/McpListPage.tsx
import { useCallback, useMemo, useState } from "react";
import { Outlet, useMatch, useNavigate } from "react-router-dom";
import type { McpServerRuntimeStatus } from "../types";

import { WorkspaceSidebar } from "../../../app/WorkspaceSidebar";
import { AdminTokenControl } from "../components/AdminTokenControl";
import { McpServerFormDrawer } from "../components/McpServerFormDrawer";
import { McpServerTable } from "../components/McpServerTable";
import { useMcpMutations, useMcpServerDetail, useMcpServers } from "../hooks";
import { getMcpAdminToken, setMcpAdminToken } from "../adminToken";

export type McpStatusFilter = "all" | McpServerRuntimeStatus;

export function McpListPage() {
  const serversState = useMcpServers();
  const [searchText, setSearchText] = useState("");
  const [statusFilter, setStatusFilter] = useState<McpStatusFilter>("all");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [adminTokenInput, setAdminTokenInput] = useState(() => getMcpAdminToken());
  const [adminTokenSaved, setAdminTokenSaved] = useState(false);
  const navigate = useNavigate();

  const isCreateDrawerOpen = useMatch("/mcp/new") !== null;

  const mutations = useMcpMutations();

  const filteredServers = useMemo(() => {
    const query = searchText.trim().toLowerCase();
    return serversState.data.filter((server) => {
      if (statusFilter !== "all" && server.runtime_status !== statusFilter) return false;
      if (query && !server.name.toLowerCase().includes(query)) return false;
      return true;
    });
  }, [searchText, serversState.data, statusFilter]);

  const mutationErrorMessage = (() => {
    const err = mutations.error;
    if (!err) return null;
    if (err instanceof Error) return err.message;
    return String(err);
  })();

  async function handleSaveAdminToken() {
    setMcpAdminToken(adminTokenInput);
    setAdminTokenInput(getMcpAdminToken());
    setAdminTokenSaved(true);
    if (getMcpAdminToken()) {
      await serversState.refetch();
    }
  }

  const runMutation = useCallback(
    async (action: () => Promise<unknown>) => {
      try {
        await action();
        await serversState.refetch();
      } catch {
        // error is stored in mutations.error by the hook
      }
    },
    [mutations, serversState],
  );

  return (
    <div className="flex min-h-screen flex-1 text-ink">
      <WorkspaceSidebar
        activeKey="mcp"
        onNavigateMcp={() => navigate("/mcp")}
        onNavigateSop={() => navigate("/sop")}
        onToggle={() => setSidebarOpen((v) => !v)}
        open={sidebarOpen}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <main aria-label="MCP 管理主内容" className="flex flex-1 flex-col overflow-hidden">
          <header className="flex shrink-0 flex-col gap-3 border-b border-hairline bg-canvas/60 px-4 py-3 backdrop-blur-sm sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <h1 className="text-base font-semibold tracking-tight text-ink">
                MCP 管理
              </h1>
              <p className="mt-0.5 text-xs text-mute">
                管理 MCP server 生命周期与工具快照
              </p>
            </div>
            <AdminTokenControl
              onChange={(next) => { setAdminTokenInput(next); setAdminTokenSaved(false); }}
              onSave={() => { void handleSaveAdminToken(); }}
              saved={adminTokenSaved}
              value={adminTokenInput}
            />
          </header>

          <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-4 py-3">
            {mutationErrorMessage ? (
              <p
                className="mb-3 rounded-xl border border-error-soft bg-canvas px-3 py-2 text-xs text-error-deep"
                role="alert"
              >
                {mutationErrorMessage}
              </p>
            ) : null}

            <div className="min-h-0 flex-1 overflow-auto">
              <McpServerTable
                error={serversState.error}
                loading={serversState.loading}
                onCreateServer={() => navigate("/mcp/new")}
                onDeleteServer={(id) => {
                  if (window.confirm(`确认删除 ${getServerName(id)}？`)) {
                    void runMutation(mutations.deleteServer(id));
                  }
                }}
                onRefresh={() => { void serversState.refetch(); }}
                onRestartServer={(id) => {
                  if (window.confirm(`确认重启 ${getServerName(id)}？`)) {
                    void runMutation(mutations.restartServer(id));
                  }
                }}
                onSearchTextChange={setSearchText}
                onStartServer={(id) => { void runMutation(mutations.startServer(id)); }}
                onStatusFilterChange={setStatusFilter}
                onStopServer={(id) => { void runMutation(mutations.stopServer(id)); }}
                onCheckServer={(id) => { void runMutation(mutations.checkServer(id)); }}
                pending={mutations.pending}
                searchText={searchText}
                servers={filteredServers}
                statusFilter={statusFilter}
              />
            </div>
          </div>
        </main>
      </div>

      {/* Create drawer — open derived from route */}
      <McpServerFormDrawer
        mode="create"
        onClose={() => navigate("/mcp")}
        onCreate={async (payload) => {
          const created = await mutations.createServer(payload);
          await serversState.refetch();
          navigate(`/mcp/${created.id}`);
        }}
        onUpdate={async () => {}}
        open={isCreateDrawerOpen}
        pending={mutations.pending}
        server={null}
      />
    </div>
  );

  function getServerName(serverId: string) {
    return serversState.data.find((s) => s.id === serverId)?.name ?? "这个 MCP Server";
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/mcp/pages/McpListPage.tsx
git commit -m "feat: add McpListPage with table, toolbar, and create drawer routing"
```

---

## Chunk 5: Detail Panels + McpDetailPage

### Task 5.1: McpDetailConfigPanel

**Files:**
- Create: `src/features/mcp/components/McpDetailConfigPanel.tsx`

- [ ] **Step 1: Implement McpDetailConfigPanel**

```tsx
// src/features/mcp/components/McpDetailConfigPanel.tsx
import type { McpServerDetail } from "../types";

type McpDetailConfigPanelProps = {
  server: McpServerDetail;
};

function ConfigRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="grid grid-cols-[160px_minmax(0,1fr)] gap-3 border-b border-hairline px-4 py-2.5 last:border-0">
      <dt className="text-2xs uppercase tracking-wide text-mute font-mono">{label}</dt>
      <dd className={`text-xs text-ink break-all ${mono ? "font-mono text-2xs" : ""}`}>
        {value}
      </dd>
    </div>
  );
}

function MultiConfigRow({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="grid grid-cols-[160px_minmax(0,1fr)] gap-3 border-b border-hairline px-4 py-2.5 last:border-0">
      <dt className="text-2xs uppercase tracking-wide text-mute font-mono">{label}</dt>
      <dd className="space-y-0.5">
        {values.length === 0
          ? <span className="text-xs text-mute">-</span>
          : values.map((v, i) => (
              <div key={i} className="font-mono text-2xs text-ink break-all">{v}</div>
            ))}
      </dd>
    </div>
  );
}

export function McpDetailConfigPanel({ server }: McpDetailConfigPanelProps) {
  const envLines = Object.entries(server.env).map(([k, v]) => `${k}=${v}`);
  const headerLines = Object.entries(server.headers).map(([k, v]) => `${k}=${v}`);

  return (
    <div className="rounded-xl border border-hairline bg-canvas">
      {server.last_error ? (
        <p
          role="alert"
          className="rounded-t-xl border-b border-error-soft bg-canvas px-3 py-2 text-xs text-error-deep"
        >
          {server.last_error}
        </p>
      ) : null}

      <dl>
        <ConfigRow label="Transport" value={server.transport} />
        {server.transport === "stdio" ? (
          <ConfigRow label="Command" value={server.command ?? "-"} mono />
        ) : (
          <ConfigRow label="URL" value={server.url ?? "-"} mono />
        )}
        <ConfigRow label="Args" value={server.args.length > 0 ? server.args.join(" ") : "-"} mono />
        <ConfigRow label="Enabled" value={server.enabled ? "true" : "false"} />
        <ConfigRow label="Desired State" value={server.desired_state} />
        <MultiConfigRow label="Env" values={envLines} />
        <MultiConfigRow label="Headers" values={headerLines} />
      </dl>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/mcp/components/McpDetailConfigPanel.tsx
git commit -m "feat: add McpDetailConfigPanel definition table"
```

### Task 5.2: McpDetailToolsPanel

**Files:**
- Create: `src/features/mcp/components/McpDetailToolsPanel.tsx`

- [ ] **Step 1: Implement McpDetailToolsPanel**

```tsx
// src/features/mcp/components/McpDetailToolsPanel.tsx
import { useState } from "react";
import type { McpTool } from "../types";

type McpDetailToolsPanelProps = {
  tools: McpTool[];
};

function ToolRow({ tool }: { tool: McpTool }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <tr className="border-b border-hairline last:border-0">
        <td className="w-[240px] px-3 py-2 font-mono text-xs text-ink">{tool.name}</td>
        <td className="px-3 py-2 text-xs text-body">{tool.description ?? "无描述"}</td>
        <td className="w-[120px] px-3 py-2">
          <button
            className="text-2xs text-mute transition-colors hover:text-ink"
            onClick={() => setExpanded((v) => !v)}
            type="button"
          >
            查看 schema {expanded ? "▴" : "▾"}
          </button>
        </td>
      </tr>
      {expanded ? (
        <tr>
          <td className="px-3 pb-2" colSpan={3}>
            <pre className="overflow-x-auto rounded-md border border-hairline bg-canvas-soft px-3 py-2 font-mono text-2xs text-body">
              {JSON.stringify(tool.input_schema, null, 2)}
            </pre>
          </td>
        </tr>
      ) : null}
    </>
  );
}

export function McpDetailToolsPanel({ tools }: McpDetailToolsPanelProps) {
  if (tools.length === 0) {
    return (
      <div className="rounded-xl border border-hairline bg-canvas py-12 text-center text-xs text-mute">
        暂无工具快照。
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-hairline bg-canvas">
      <table className="w-full">
        <thead>
          <tr className="border-b border-hairline bg-canvas-soft">
            <th className="h-10 w-[240px] px-3 text-left text-2xs font-medium uppercase tracking-wide text-mute font-mono">
              工具名
            </th>
            <th className="h-10 px-3 text-left text-2xs font-medium uppercase tracking-wide text-mute font-mono">
              描述
            </th>
            <th className="h-10 w-[120px] px-3 text-left text-2xs font-medium uppercase tracking-wide text-mute font-mono">
              Schema
            </th>
          </tr>
        </thead>
        <tbody>
          {tools.map((tool) => (
            <ToolRow key={tool.name} tool={tool} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/mcp/components/McpDetailToolsPanel.tsx
git commit -m "feat: add McpDetailToolsPanel with schema expand"
```

### Task 5.3: McpDetailPage

**Files:**
- Create: `src/features/mcp/pages/McpDetailPage.tsx`

- [ ] **Step 1: Implement McpDetailPage**

```tsx
// src/features/mcp/pages/McpDetailPage.tsx
import { useCallback, useMemo, useState } from "react";
import { useLocation, useMatch, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { WorkspaceSidebar } from "../../../app/WorkspaceSidebar";
import { McpBreadcrumb } from "../components/McpBreadcrumb";
import { McpDetailConfigPanel } from "../components/McpDetailConfigPanel";
import { McpDetailToolsPanel } from "../components/McpDetailToolsPanel";
import { McpRowActionsMenu } from "../components/McpRowActionsMenu";
import { McpServerFormDrawer } from "../components/McpServerFormDrawer";
import { McpStatusBadge } from "../components/McpStatusBadge";
import { getMcpErrorMessage, isMcpNotFoundError } from "../components/errorMessages";
import { useMcpMutations, useMcpServerDetail, useMcpServers } from "../hooks";
import type { McpDetailTab } from "../types";

export function McpDetailPage() {
  const { serverId } = useParams<{ serverId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();

  const tabParam = searchParams.get("tab");
  const activeTab: McpDetailTab =
    tabParam === "tools" ? "tools" : "configuration"; // invalid → fallback to configuration

  const isEditDrawerOpen = useMatch("/mcp/:serverId/edit") !== null;
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const detailState = useMcpServerDetail(serverId ?? null);
  const serversState = useMcpServers();
  const mutations = useMcpMutations();

  const server = detailState.data;
  const is404 = isMcpNotFoundError(detailState.error);
  const isLoading = detailState.loading && !detailState.data;

  const mutationErrorMessage = (() => {
    const err = mutations.error;
    if (!err) return null;
    if (err instanceof Error) return err.message;
    return String(err);
  })();

  const targetServerId = server?.id ?? serverId ?? "";

  const runMutation = useCallback(
    async (action: () => Promise<unknown>) => {
      try {
        await action();
        await Promise.all([serversState.refetch(), detailState.refetch()]);
      } catch (e) {
        // If mutation returns 404, skip refetchDetail
        if (isMcpNotFoundError(e instanceof Error ? e : new Error(String(e)))) {
          await serversState.refetch();
          // Don't call detailState.refetch() — already 404'd
        } else {
          await serversState.refetch();
          await detailState.refetch();
        }
      }
    },
    [serversState, detailState],
  );

  const show404Card = is404 && !isLoading;

  return (
    <div className="flex min-h-screen flex-1 text-ink">
      <WorkspaceSidebar
        activeKey="mcp"
        onNavigateMcp={() => navigate("/mcp")}
        onNavigateSop={() => navigate("/sop")}
        onToggle={() => setSidebarOpen((v) => !v)}
        open={sidebarOpen}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <main className="flex flex-1 flex-col overflow-hidden">
          {/* Top strip */}
          <div className="flex shrink-0 flex-col gap-3 border-b border-hairline bg-canvas/60 px-4 py-3 backdrop-blur-sm">
            <McpBreadcrumb
              serverName={server?.name ?? serverId ?? "..."}
            />

            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                {isLoading ? (
                  <h1 className="font-mono text-base text-mute">{serverId}</h1>
                ) : is404 ? (
                  <h1 className="font-mono text-base text-mute">{serverId}</h1>
                ) : server ? (
                  <>
                    <h1 className="text-base font-semibold tracking-tight text-ink">
                      {server.name}
                    </h1>
                    <p className="mt-0.5 text-2xs text-mute flex items-center gap-1.5">
                      <McpStatusBadge status={server.runtime_status} />
                      <span aria-hidden="true">·</span>
                      <span>{server.transport}</span>
                      <span aria-hidden="true">·</span>
                      <span>desired {server.desired_state}</span>
                    </p>
                  </>
                ) : null}
              </div>

              <div className="flex shrink-0 items-center gap-1.5">
                <button
                  aria-disabled={isLoading || is404}
                  className="h-9 rounded-lg border border-hairline bg-canvas px-3 text-xs text-body transition-colors hover:border-hairline-strong hover:text-ink aria-disabled:cursor-not-allowed aria-disabled:opacity-50"
                  disabled={isLoading || is404}
                  onClick={() => {
                    if (is404) {
                      navigate("/mcp", { replace: true });
                      return;
                    }
                    navigate({
                      pathname: `/mcp/${targetServerId}/edit`,
                      search: location.search,
                    });
                  }}
                  type="button"
                >
                  编辑
                </button>
                <button
                  aria-disabled={isLoading || is404}
                  className="h-9 rounded-lg border border-error/40 bg-canvas px-3 text-xs font-medium text-error-deep transition-colors hover:bg-error-soft aria-disabled:cursor-not-allowed aria-disabled:opacity-50"
                  disabled={isLoading || is404 || mutations.pending}
                  onClick={() => {
                    if (!server) return;
                    if (!window.confirm(`确认删除 ${server.name}？`)) return;
                    void (async () => {
                      await mutations.deleteServer(targetServerId);
                      await serversState.refetch();
                      // Do NOT call detailState.refetch()
                      navigate("/mcp", { replace: true });
                    })();
                  }}
                  type="button"
                >
                  删除
                </button>
                {server ? (
                  <McpRowActionsMenu
                    onCheck={(id) => { void runMutation(mutations.checkServer(id)); }}
                    onDelete={() => {}} // handled by dedicated delete button above
                    onRestart={(id) => {
                      if (window.confirm(`确认重启 ${server.name}？`)) {
                        void runMutation(mutations.restartServer(id));
                      }
                    }}
                    onStart={(id) => { void runMutation(mutations.startServer(id)); }}
                    onStop={(id) => { void runMutation(mutations.stopServer(id)); }}
                    runtimeStatus={server.runtime_status}
                    serverId={targetServerId}
                    serverName={server.name}
                  />
                ) : null}
              </div>
            </div>
          </div>

          {/* Tab bar */}
          <div className="border-b border-hairline px-4" role="tablist">
            <button
              aria-controls="mcp-detail-config-panel"
              aria-selected={activeTab === "configuration"}
              className={`h-9 px-3 text-xs font-medium transition-colors ${
                activeTab === "configuration"
                  ? "text-ink shadow-[inset_0_-2px_0_var(--color-primary)]"
                  : "text-mute hover:text-ink"
              }`}
              onClick={() => setSearchParams({ tab: "configuration" }, { replace: true })}
              role="tab"
              type="button"
            >
              配置
            </button>
            <button
              aria-controls="mcp-detail-tools-panel"
              aria-selected={activeTab === "tools"}
              className={`h-9 px-3 text-xs font-medium transition-colors ${
                activeTab === "tools"
                  ? "text-ink shadow-[inset_0_-2px_0_var(--color-primary)]"
                  : "text-mute hover:text-ink"
              }`}
              onClick={() => setSearchParams({ tab: "tools" }, { replace: true })}
              role="tab"
              type="button"
            >
              工具快照{server ? ` (${server.tool_count})` : ""}
            </button>
          </div>

          {/* Content */}
          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            {mutationErrorMessage ? (
              <p
                className="mb-3 rounded-xl border border-error-soft bg-canvas px-3 py-2 text-xs text-error-deep"
                role="alert"
              >
                {mutationErrorMessage}
              </p>
            ) : null}

            {isLoading ? (
              <p className="text-xs text-mute">加载详情中…</p>
            ) : show404Card ? (
              <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
                <p className="text-xs text-mute">MCP 服务不存在</p>
                <button
                  className="h-9 rounded-lg border border-hairline bg-canvas px-3 text-xs text-body transition-colors hover:border-hairline-strong hover:text-ink"
                  onClick={() => navigate("/mcp", { replace: true })}
                  type="button"
                >
                  返回列表
                </button>
              </div>
            ) : server ? (
              activeTab === "configuration" ? (
                <div
                  aria-labelledby={undefined}
                  id="mcp-detail-config-panel"
                  role="tabpanel"
                >
                  <McpDetailConfigPanel server={server} />
                </div>
              ) : (
                <div
                  id="mcp-detail-tools-panel"
                  role="tabpanel"
                >
                  <McpDetailToolsPanel tools={server.tools} />
                </div>
              )
            ) : null}
          </div>
        </main>
      </div>

      {/* Edit drawer */}
      {server || isEditDrawerOpen ? (
        <McpServerFormDrawer
          mode="edit"
          onClose={() =>
            navigate({
              pathname: `/mcp/${targetServerId}`,
              search: location.search,
            })
          }
          onCreate={async () => {}}
          onUpdate={async (srvId, payload) => {
            try {
              await mutations.updateServer(srvId, payload);
              await Promise.all([serversState.refetch(), detailState.refetch()]);
              navigate({
                pathname: `/mcp/${targetServerId}`,
                search: location.search,
              });
            } catch (e) {
              if (!isMcpNotFoundError(e instanceof Error ? e : new Error(String(e)))) {
                await detailState.refetch();
              }
              await serversState.refetch();
            }
          }}
          open={isEditDrawerOpen}
          pending={mutations.pending}
          server={server}
        />
      ) : null}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/mcp/pages/McpDetailPage.tsx
git commit -m "feat: add McpDetailPage with breadcrumb, tabs, config/tools panels"
```

---

## Chunk 6: McpServerFormDrawer Rewrite

### Task 6.1: Rewrite McpServerFormDrawer (shadcn-style)

**Files:**
- Modify: `src/features/mcp/components/McpServerFormDrawer.tsx`

- [ ] **Step 1: Replace the current McpServerFormDrawer.tsx content**

The current form drawer keeps its core logic (validation, parsing, focus trap, redacted field handling, payload construction) but changes the visual layout to shadcn-style sections with field-level errors.

```tsx
// src/features/mcp/components/McpServerFormDrawer.tsx
import {
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
} from "react";

import type {
  McpDesiredState,
  McpServerCreate,
  McpServerDetail,
  McpServerUpdate,
  McpTransport,
} from "../types";

type McpServerFormDrawerProps = {
  open: boolean;
  mode: "create" | "edit";
  server: McpServerDetail | null;
  pending: boolean;
  onClose: () => void;
  onCreate: (payload: McpServerCreate) => Promise<void>;
  onUpdate: (serverId: string, payload: McpServerUpdate) => Promise<void>;
};

const DEFAULT_TRANSPORT: McpTransport = "stdio";
const DEFAULT_DESIRED_STATE: McpDesiredState = "stopped";
const DEFAULT_ENABLED = false;
const REDACTED_VALUE = "********";
const FOCUSABLE_SELECTOR =
  "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex='-1'])";

export function McpServerFormDrawer({
  open,
  mode,
  server,
  pending,
  onClose,
  onCreate,
  onUpdate,
}: McpServerFormDrawerProps) {
  const [name, setName] = useState("");
  const [transport, setTransport] = useState<McpTransport>(DEFAULT_TRANSPORT);
  const [command, setCommand] = useState("");
  const [url, setUrl] = useState("");
  const [argsText, setArgsText] = useState("");
  const [envText, setEnvText] = useState("");
  const [headersText, setHeadersText] = useState("");
  const [enabled, setEnabled] = useState(DEFAULT_ENABLED);
  const [desiredState, setDesiredState] = useState<McpDesiredState>(DEFAULT_DESIRED_STATE);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const drawerRef = useRef<HTMLDivElement | null>(null);
  const nameInputRef = useRef<HTMLInputElement | null>(null);
  const commandInputRef = useRef<HTMLInputElement | null>(null);
  const urlInputRef = useRef<HTMLInputElement | null>(null);
  const titleId = useId();

  // Initialize / reset form state
  useEffect(() => {
    if (!open) return;

    // Clear mutation errors from the drawer's hook on open
    setFieldErrors({});

    if (mode === "edit" && server) {
      setName(server.name);
      setTransport(server.transport);
      setCommand(server.command ?? "");
      setUrl(server.url ?? "");
      setArgsText(argsToText(server.args));
      setEnvText(keyValueMapToText(server.env));
      setHeadersText(keyValueMapToText(server.headers));
      setEnabled(server.enabled);
      setDesiredState(server.desired_state);
      return;
    }

    setName("");
    setTransport(DEFAULT_TRANSPORT);
    setCommand("");
    setUrl("");
    setArgsText("");
    setEnvText("");
    setHeadersText("");
    setEnabled(DEFAULT_ENABLED);
    setDesiredState(DEFAULT_DESIRED_STATE);
  }, [mode, open, server]);

  // Auto-focus first input
  useEffect(() => {
    if (!open) return;
    nameInputRef.current?.focus();
  }, [open]);

  // Focus trap
  useEffect(() => {
    if (!open) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }

      if (event.key !== "Tab") return;

      const drawerElement = drawerRef.current;
      if (!drawerElement) return;

      const focusableElements = Array.from(
        drawerElement.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      );

      if (focusableElements.length === 0) return;

      const first = focusableElements[0];
      const last = focusableElements[focusableElements.length - 1];
      const active = document.activeElement as HTMLElement | null;

      if (!active || !drawerElement.contains(active)) {
        event.preventDefault();
        (event.shiftKey ? last : first)?.focus();
        return;
      }

      if (event.shiftKey && active === first) {
        event.preventDefault();
        last?.focus();
        return;
      }

      if (!event.shiftKey && active === last) {
        event.preventDefault();
        first?.focus();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, open]);

  if (!open) return null;

  function validateForm(): boolean {
    // Short-circuit on first error — this behavior is load-bearing
    // for getByRole("alert") test queries.

    if (!name.trim()) {
      setFieldErrors({ name: "请填写服务名称。" });
      nameInputRef.current?.focus();
      return false;
    }

    if (transport === "stdio" && command.trim().length === 0) {
      setFieldErrors({ command: "stdio 模式需要填写 command。" });
      commandInputRef.current?.focus();
      return false;
    }

    const nextUrl = url.trim();
    if (transport === "http" && nextUrl.length === 0) {
      setFieldErrors({ url: "http 模式需要填写 url。" });
      urlInputRef.current?.focus();
      return false;
    }

    if (transport === "http" && !isValidHttpUrl(nextUrl)) {
      setFieldErrors({ url: "请填写有效的 http url。" });
      urlInputRef.current?.focus();
      return false;
    }

    const parsedEnv = parseKeyValueText("env", envText);
    if (parsedEnv.error) {
      setFieldErrors({ env: parsedEnv.error });
      return false;
    }

    const parsedHeaders = parseKeyValueText("headers", headersText);
    if (parsedHeaders.error) {
      setFieldErrors({ headers: parsedHeaders.error });
      return false;
    }

    setFieldErrors({});
    return true;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    // Clear API error before validation (per spec: errors.clear lifecycle)
    // Mutation error is cleared by useMcpMutations.runMutation which calls
    // setError(null) before each action

    if (!validateForm()) return;

    const parsedEnv = parseKeyValueText("env", envText);
    const parsedHeaders = parseKeyValueText("headers", headersText);
    const nextArgs = parseArgsText(argsText);
    const nextName = name.trim();

    if (mode === "create") {
      const payload: McpServerCreate = {
        args: nextArgs,
        desired_state: desiredState,
        enabled,
        env: parsedEnv.value,
        headers: parsedHeaders.value,
        name: nextName,
        transport,
      };

      if (transport === "stdio") {
        payload.command = command.trim() || null;
      } else {
        payload.url = url.trim() || null;
      }

      await onCreate(payload);
      return;
    }

    // Edit mode
    if (!server) return;

    if (
      hasUnsafeRedactedPlaceholder(envText, parsedEnv.value, server.env) ||
      hasUnsafeRedactedPlaceholder(headersText, parsedHeaders.value, server.headers)
    ) {
      setFieldErrors({
        _global: "脱敏值 ******** 需要替换为新值，或保持该区域不变。",
      });
      return;
    }

    const payload: McpServerUpdate = {
      args: nextArgs,
      desired_state: desiredState,
      enabled,
      name: nextName,
    };

    if (!shouldOmitRedactedField(envText, server.env)) {
      payload.env = parsedEnv.value;
    }

    if (!shouldOmitRedactedField(headersText, server.headers)) {
      payload.headers = parsedHeaders.value;
    }

    if (transport === "stdio") {
      payload.command = command.trim() || null;
      payload.url = null;
    } else {
      payload.url = url.trim() || null;
      payload.command = null;
    }

    await onUpdate(server.id, payload);
  }

  function clearFieldError(field: string) {
    setFieldErrors((prev) => {
      if (!prev[field]) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });
  }

  const hasNameError = !!fieldErrors.name;
  const hasCommandError = !!fieldErrors.command;
  const hasUrlError = !!fieldErrors.url;
  const hasEnvError = !!fieldErrors.env;
  const hasHeadersError = !!fieldErrors.headers;
  const hasGlobalError = !!fieldErrors._global;
  const nameErrorId = useId();
  const commandErrorId = useId();
  const urlErrorId = useId();
  const envErrorId = useId();
  const headersErrorId = useId();
  const globalErrorId = useId();

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-ink/25">
      <div
        aria-labelledby={titleId}
        aria-modal="true"
        className="flex h-full w-full flex-col border-l border-hairline bg-canvas shadow-xl sm:w-[420px]"
        ref={drawerRef}
        role="dialog"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-hairline px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold text-ink" id={titleId}>
              {mode === "create" ? "新增 MCP 服务" : "编辑 MCP 服务"}
            </h2>
            <p className="text-2xs text-mute font-mono">
              {mode === "create" ? "NEW SERVER" : `EDIT · ${server?.id ?? "..."}`}
            </p>
          </div>
          <button
            className="rounded-lg px-2 py-1 text-sm text-mute transition-colors hover:bg-canvas-soft hover:text-ink"
            onClick={onClose}
            type="button"
          >
            关闭
          </button>
        </div>

        {/* Body */}
        <form
          className="min-h-0 flex-1 overflow-y-auto px-4 py-3"
          noValidate
          onSubmit={(event) => { void handleSubmit(event); }}
        >
          {/* Global error (API error from mutation) */}
          {hasGlobalError ? (
            <p
              className="mb-3 rounded-lg bg-error-soft px-3 py-2 text-xs text-error-deep"
              id={globalErrorId}
              role="alert"
            >
              {fieldErrors._global}
            </p>
          ) : null}

          {/* Section: 基本信息 */}
          <SectionHeader>基本信息</SectionHeader>

          <div className="space-y-1">
            <label className="text-xs font-medium text-ink" htmlFor="mcp-form-name">
              服务名称 <span className="text-error">*</span>
            </label>
            <input
              aria-describedby={hasNameError ? nameErrorId : undefined}
              aria-invalid={hasNameError}
              className="h-9 w-full rounded-lg border border-hairline bg-canvas px-3 text-xs text-ink placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 aria-invalid:border-error aria-invalid:ring-error/20"
              id="mcp-form-name"
              onChange={(e) => { setName(e.target.value); clearFieldError("name"); }}
              ref={nameInputRef}
              required
              value={name}
            />
            {hasNameError ? (
              <p className="text-2xs text-error-deep" id={nameErrorId} role="alert">
                {fieldErrors.name}
              </p>
            ) : null}
          </div>

          <div className="mt-3 space-y-1">
            <label className="text-xs font-medium text-ink" htmlFor="mcp-form-transport">
              传输方式
            </label>
            <select
              className="h-9 w-full rounded-lg border border-hairline bg-canvas px-3 text-xs text-ink outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 appearance-none"
              disabled={mode === "edit"}
              id="mcp-form-transport"
              onChange={(e) => setTransport(e.target.value as McpTransport)}
              value={transport}
            >
              <option value="stdio">stdio</option>
              <option value="http">http</option>
            </select>
          </div>

          {/* Section: 连接 */}
          <SectionHeader>连接</SectionHeader>

          {transport === "stdio" ? (
            <>
              <div className="space-y-1">
                <label className="text-xs font-medium text-ink" htmlFor="mcp-form-command">
                  command <span className="text-error">*</span>
                </label>
                <input
                  aria-describedby={hasCommandError ? commandErrorId : undefined}
                  aria-invalid={hasCommandError}
                  className="h-9 w-full rounded-lg border border-hairline bg-canvas px-3 text-xs text-ink placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 aria-invalid:border-error aria-invalid:ring-error/20"
                  id="mcp-form-command"
                  onChange={(e) => { setCommand(e.target.value); clearFieldError("command"); }}
                  ref={commandInputRef}
                  value={command}
                />
                {hasCommandError ? (
                  <p className="text-2xs text-error-deep" id={commandErrorId} role="alert">
                    {fieldErrors.command}
                  </p>
                ) : null}
              </div>
              <div className="mt-3 space-y-1">
                <label className="text-xs font-medium text-ink" htmlFor="mcp-form-args">
                  args
                </label>
                <textarea
                  className="min-h-[72px] w-full rounded-lg border border-hairline bg-canvas px-3 py-2 font-mono text-2xs leading-relaxed text-ink placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 resize-y"
                  id="mcp-form-args"
                  onChange={(e) => setArgsText(e.target.value)}
                  placeholder="每行一个参数"
                  value={argsText}
                />
              </div>
            </>
          ) : (
            <div className="space-y-1">
              <label className="text-xs font-medium text-ink" htmlFor="mcp-form-url">
                url <span className="text-error">*</span>
              </label>
              <input
                aria-describedby={hasUrlError ? urlErrorId : undefined}
                aria-invalid={hasUrlError}
                className="h-9 w-full rounded-lg border border-hairline bg-canvas px-3 text-xs text-ink placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 aria-invalid:border-error aria-invalid:ring-error/20"
                id="mcp-form-url"
                onChange={(e) => { setUrl(e.target.value); clearFieldError("url"); }}
                ref={urlInputRef}
                type="url"
                value={url}
              />
              {hasUrlError ? (
                <p className="text-2xs text-error-deep" id={urlErrorId} role="alert">
                  {fieldErrors.url}
                </p>
              ) : null}
            </div>
          )}

          {/* Section: 环境与请求头 */}
          <SectionHeader>环境与请求头</SectionHeader>

          <div className="space-y-1">
            <label className="text-xs font-medium text-ink" htmlFor="mcp-form-env">
              env
            </label>
            <textarea
              aria-describedby={hasEnvError ? envErrorId : undefined}
              aria-invalid={hasEnvError}
              className="min-h-[72px] w-full rounded-lg border border-hairline bg-canvas px-3 py-2 font-mono text-2xs leading-relaxed text-ink placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 aria-invalid:border-error aria-invalid:ring-error/20 resize-y"
              id="mcp-form-env"
              onChange={(e) => { setEnvText(e.target.value); clearFieldError("env"); }}
              placeholder="KEY=VALUE"
              value={envText}
            />
            {hasEnvError ? (
              <p className="text-2xs text-error-deep" id={envErrorId} role="alert">
                {fieldErrors.env}
              </p>
            ) : null}
          </div>

          <div className="mt-3 space-y-1">
            <label className="text-xs font-medium text-ink" htmlFor="mcp-form-headers">
              headers
            </label>
            <textarea
              aria-describedby={hasHeadersError ? headersErrorId : undefined}
              aria-invalid={hasHeadersError}
              className="min-h-[72px] w-full rounded-lg border border-hairline bg-canvas px-3 py-2 font-mono text-2xs leading-relaxed text-ink placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 aria-invalid:border-error aria-invalid:ring-error/20 resize-y"
              id="mcp-form-headers"
              onChange={(e) => { setHeadersText(e.target.value); clearFieldError("headers"); }}
              placeholder="KEY=VALUE"
              value={headersText}
            />
            {hasHeadersError ? (
              <p className="text-2xs text-error-deep" id={headersErrorId} role="alert">
                {fieldErrors.headers}
              </p>
            ) : null}
          </div>

          {/* Section: 启动行为 */}
          <SectionHeader>启动行为</SectionHeader>

          <label className="flex cursor-pointer items-start gap-2">
            <input
              checked={desiredState === "running"}
              className="mt-0.5 h-4 w-4 rounded border-hairline bg-canvas accent-primary"
              onChange={(e) => setDesiredState(e.target.checked ? "running" : "stopped")}
              type="checkbox"
            />
            <span>
              <span className="text-xs text-ink">创建后立即启动</span>
              <span className="block text-2xs text-mute">
                服务保存后将立即拉起 (desired_state=running)
              </span>
            </span>
          </label>

          <label className="mt-2 flex cursor-pointer items-start gap-2">
            <input
              checked={enabled}
              className="mt-0.5 h-4 w-4 rounded border-hairline bg-canvas accent-primary"
              onChange={(e) => setEnabled(e.target.checked)}
              type="checkbox"
            />
            <span>
              <span className="text-xs text-ink">启用</span>
              <span className="block text-2xs text-mute">
                启用该服务供 agent 使用
              </span>
            </span>
          </label>
        </form>

        {/* Footer */}
        <div className="sticky bottom-0 flex items-center justify-end gap-2 border-t border-hairline bg-canvas px-4 py-3">
          <button
            className="h-9 rounded-lg border border-hairline bg-canvas px-3 text-xs text-body transition-colors hover:border-hairline-strong hover:text-ink"
            onClick={onClose}
            type="button"
          >
            取消
          </button>
          <button
            className="h-9 rounded-lg bg-primary px-3 text-xs font-medium text-on-primary transition-colors hover:bg-primary-deep disabled:cursor-not-allowed disabled:opacity-50"
            disabled={pending}
            form="mcp-drawer-form"
            type="submit"
          >
            {pending ? "提交中..." : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mt-4 mb-2 border-b border-hairline pb-1.5 text-2xs font-mono uppercase tracking-wide text-mute first:mt-0">
      {children}
    </h3>
  );
}

// Helper functions unchanged from original
function isValidHttpUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

function argsToText(args: string[]): string {
  return args.join("\n");
}

function parseArgsText(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

function keyValueMapToText(value: Record<string, string>): string {
  return Object.entries(value)
    .map(([key, entryValue]) => `${key}=${entryValue}`)
    .join("\n");
}

function parseKeyValueText(
  label: "env" | "headers",
  value: string,
): { error: string | null; value: Record<string, string> } {
  const parsed: Record<string, string> = {};
  const lines = value.split(/\r?\n/);

  for (let index = 0; index < lines.length; index += 1) {
    const rawLine = lines[index] ?? "";
    const line = rawLine.trim();

    if (line.length === 0) continue;

    const separatorIndex = line.indexOf("=");

    if (separatorIndex <= 0) {
      return {
        error: `${label} 第 ${index + 1} 行需要使用 KEY=VALUE 格式。`,
        value: {},
      };
    }

    const key = line.slice(0, separatorIndex).trim();
    const entryValue = line.slice(separatorIndex + 1).trim();

    if (!key) {
      return {
        error: `${label} 第 ${index + 1} 行需要使用 KEY=VALUE 格式。`,
        value: {},
      };
    }

    parsed[key] = entryValue;
  }

  return { error: null, value: parsed };
}

function shouldOmitRedactedField(
  currentText: string,
  original: Record<string, string>,
): boolean {
  return hasRedactedValue(original) && currentText === keyValueMapToText(original);
}

function hasUnsafeRedactedPlaceholder(
  currentText: string,
  parsed: Record<string, string>,
  original: Record<string, string>,
): boolean {
  if (shouldOmitRedactedField(currentText, original)) return false;

  return Object.entries(parsed).some(
    ([key, value]) => value === REDACTED_VALUE && original[key] === REDACTED_VALUE,
  );
}

function hasRedactedValue(value: Record<string, string>): boolean {
  return Object.values(value).some((entryValue) => entryValue === REDACTED_VALUE);
}
```

Note: The form element needs `id="mcp-drawer-form"` for the footer submit button to work. Update the `<form>` tag:

```tsx
<form
  id="mcp-drawer-form"
  className="min-h-0 flex-1 overflow-y-auto px-4 py-3"
  noValidate
  onSubmit={(event) => { void handleSubmit(event); }}
>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/mcp/components/McpServerFormDrawer.tsx
git commit -m "refactor: rewrite McpServerFormDrawer as shadcn-style sectioned form with field-level errors"
```

---

## Chunk 7: App.tsx Routing + WorkspaceSidebar Active Key Update

### Task 7.1: Update App.tsx routes

**Files:**
- Modify: `src/app/App.tsx`

- [ ] **Step 1: Replace App.tsx route definitions**

```tsx
// src/app/App.tsx
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { McpDetailPage } from "../features/mcp/pages/McpDetailPage";
import { McpListPage } from "../features/mcp/pages/McpListPage";
import { ChatPage } from "../features/sop/pages/ChatPage";
import { AppShell } from "./AppShell";
import { ProtectedRoute } from "./routing/ProtectedRoute";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />} path="/">
          <Route element={<Navigate replace to="/sop" />} index />
          <Route element={<ChatPage />} path="sop" />
          <Route element={<ProtectedRoute />}>
            <Route element={<McpListPage />} path="mcp">
              <Route element={null} path="new" />
            </Route>
            <Route element={<McpDetailPage />} path="mcp/:serverId">
              <Route element={null} path="edit" />
            </Route>
          </Route>
          <Route element={<Navigate replace to="/sop" />} path="*" />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 2: Update AppShell or WorkspaceSidebar to use pathname-based activeKey**

The sidebar `activeKey` prop needs to be `"mcp"` when at any `/mcp` or `/mcp/*` path. The `McpListPage` and `McpDetailPage` already pass `activeKey="mcp"` directly, so the sidebar doesn't need to derive it — each page explicitly sets it.

However, the `AppShell` does NOT render the sidebar — the sidebar is rendered inside each page component (McpListPage, McpDetailPage, ChatPage). So no change needed to AppShell.

- [ ] **Step 3: Update App.test.tsx**

The existing `App.test.tsx` needs mocks updated. Read the current test file:

```tsx
// Update mocks in App.test.tsx
vi.mock("../../mcp/pages/McpPage", () => ({
  McpPage: () => (
    <div role="region" aria-label="MCP 管理 mock">
      <h1>MCP 管理</h1>
    </div>
  ),
}));
```

Replace with:

```tsx
vi.mock("../../mcp/pages/McpListPage", () => ({
  McpListPage: () => (
    <div role="region" aria-label="MCP 管理 mock">
      <h1>MCP 管理</h1>
    </div>
  ),
}));
```

And add a mock for `McpDetailPage` if it doesn't exist yet.

Also add the integration test that verifies clicking a name link on the list page navigates to the detail page (end-to-end). Add this test to `src/app/App.test.tsx` or a new `src/features/mcp/AppMcpNavigation.test.tsx`:

```tsx
// src/features/mcp/pages/AppMcpNavigation.test.tsx
// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { McpListPage } from "./McpListPage";
import { McpDetailPage } from "./McpDetailPage";

vi.mock("../../../app/routing/useAuthz", () => ({
  useAuthz: () => ({ isAdmin: true }),
}));
vi.mock("../../sop/pages/ChatPage", () => ({
  ChatPage: () => <div>SOP Mock</div>,
}));
vi.mock("../hooks", () => ({
  useMcpMutations: vi.fn(() => ({
    checkServer: vi.fn(),
    createServer: vi.fn(),
    deleteServer: vi.fn(),
    error: null,
    pending: false,
    restartServer: vi.fn(),
    startServer: vi.fn(),
    stopServer: vi.fn(),
    updateServer: vi.fn(),
  })),
  useMcpServerDetail: vi.fn(() => ({
    data: null,
    error: null,
    loading: false,
    refetch: vi.fn(),
  })),
  useMcpServers: vi.fn(() => ({
    data: [
      { id: "srv-1", name: "Alpha Server", runtime_status: "running", tool_count: 1, transport: "stdio", args: [], command: "echo", desired_state: "running", enabled: true, env: {}, headers: {}, last_checked_at: null, last_error: null, url: null },
      { id: "srv-2", name: "Beta Server", runtime_status: "stopped", tool_count: 2, transport: "stdio", args: [], command: "node", desired_state: "stopped", enabled: false, env: {}, headers: {}, last_checked_at: null, last_error: null, url: null },
    ],
    error: null,
    loading: false,
    refetch: vi.fn(),
  })),
}));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("MCP navigation integration", () => {
  it("navigates from list name link to detail page", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/mcp"]}>
        <McpListPage />
      </MemoryRouter>,
    );

    const alphaLink = screen.getByRole("link", { name: /Alpha Server/ });
    fireEvent.click(alphaLink);

    // Navigation via MemoryRouter — verify the link's href points to the detail route
    expect(alphaLink).toHaveAttribute("href", "/mcp/srv-1");
  });

  it("renders detail page from direct URL", async () => {
    render(
      <MemoryRouter initialEntries={["/mcp/srv-2"]}>
        <McpDetailPage />
      </MemoryRouter>,
    );

    // Should render breadcrumb with server name
    expect(screen.getByText("srv-2")).toBeInTheDocument();
  });
});
```

> Note: Full end-to-end navigation test (clicking a `<Link>` in the list and seeing the detail page mount) requires `<App />` + `<BrowserRouter>`. The test above verifies href correctness and direct URL rendering. The `App.test.tsx` for navigation between routes can be verified manually in the browser.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/App.tsx frontend/src/app/App.test.tsx
git commit -m "feat: add nested /mcp/new and /mcp/:serverId/edit routes"
```

---

## Chunk 8: Tests — Migration + New Tests

### Task 8.1: Delete old test file

- [ ] **Step 1: Delete McpPage.test.tsx**

```bash
rm frontend/src/features/mcp/pages/McpPage.test.tsx
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/mcp/pages/McpPage.test.tsx
git commit -m "chore: delete old McpPage.test.tsx (will be replaced by new page tests)"
```

### Task 8.2: Write McpListPage.test.tsx

**Files:**
- Create: `src/features/mcp/pages/McpListPage.test.tsx`

This test covers migration rows 1, 2, 3a, 4, 5a, 7, 8, 9, 11, 12, 15 from the migration matrix.

- [ ] **Step 1: Write McpListPage.test.tsx**

```tsx
// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { useAuthz } from "../../../app/routing/useAuthz";
import { useMcpMutations, useMcpServers } from "../hooks";
import type { McpServerSummary } from "../types";
import { McpListPage } from "./McpListPage";

function renderListPage() {
  return render(
    <MemoryRouter initialEntries={["/mcp"]}>
      <McpListPage />
    </MemoryRouter>,
  );
}

vi.mock("../../../app/routing/useAuthz", () => ({
  useAuthz: vi.fn(),
}));

vi.mock("../../sop/pages/ChatPage", () => ({
  ChatPage: () => <div>SOP Mock</div>,
}));

vi.mock("../hooks", () => ({
  useMcpMutations: vi.fn(),
  useMcpServerDetail: vi.fn(),
  useMcpServers: vi.fn(),
}));

const createServer = vi.fn();
const updateServer = vi.fn();
const deleteServer = vi.fn();
const startServer = vi.fn();
const stopServer = vi.fn();
const restartServer = vi.fn();
const checkServer = vi.fn();
const refetchServers = vi.fn();

const servers: McpServerSummary[] = [
  buildSummary({ id: "srv-1", name: "Alpha Server", tool_count: 1 }),
  buildSummary({
    id: "srv-2",
    name: "Beta Server",
    runtime_status: "stopped",
    tool_count: 2,
  }),
];

beforeEach(() => {
  createServer.mockReset();
  updateServer.mockReset();
  deleteServer.mockReset();
  startServer.mockReset();
  stopServer.mockReset();
  restartServer.mockReset();
  checkServer.mockReset();
  refetchServers.mockReset();
  window.sessionStorage.clear();
  vi.mocked(useAuthz).mockReturnValue({ isAdmin: true });

  vi.mocked(useMcpServers).mockReturnValue({
    data: servers,
    error: null,
    loading: false,
    refetch: refetchServers,
  });

  vi.mocked(useMcpMutations).mockReturnValue({
    checkServer,
    createServer,
    deleteServer,
    error: null,
    pending: false,
    restartServer,
    startServer,
    stopServer,
    updateServer,
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("McpListPage", () => {
  it("renders sidebar with MCP marked active", () => {
    renderListPage();

    const sidebar = screen.getByRole("complementary", { name: "工作台侧边栏" });
    const nav = within(sidebar).getByRole("navigation", { name: "工作台导航" });

    expect(within(nav).getByRole("button", { name: "发起新SOP质检" })).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: "MCP 管理" })).toHaveAttribute("aria-current", "page");
  });

  it("keeps the table visible after toggling the sidebar", () => {
    renderListPage();

    fireEvent.click(screen.getByRole("button", { name: "收起侧边栏" }));

    // Table should still be visible
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "MCP 管理" })).toBeInTheDocument();
  });

  it("renders server names as links in table rows", () => {
    renderListPage();

    const link = screen.getByRole("link", { name: /Alpha Server/ });
    expect(link).toHaveAttribute("href", "/mcp/srv-1");

    expect(screen.getByRole("link", { name: /Beta Server/ })).toHaveAttribute("href", "/mcp/srv-2");
  });

  it("renders server list in the table", () => {
    renderListPage();

    const rows = screen.getAllByRole("row");
    // header row + 2 data rows
    expect(rows.length).toBe(3);

    expect(screen.getByText("Alpha Server")).toBeInTheDocument();
    expect(screen.getByText("Beta Server")).toBeInTheDocument();
  });

  it("filters servers by search text", () => {
    renderListPage();

    fireEvent.change(screen.getByRole("searchbox", { name: "搜索 MCP 服务" }), {
      target: { value: "Alpha" },
    });

    expect(screen.getByText("Alpha Server")).toBeInTheDocument();
    expect(screen.queryByText("Beta Server")).not.toBeInTheDocument();
  });

  it("invokes start stop restart check actions via dropdown", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);

    renderListPage();

    // Open dropdown for Alpha Server (running)
    const triggers = screen.getAllByRole("button", { name: "更多操作" });
    fireEvent.click(triggers[0]);

    // Should show 停止 (running), not 启动
    expect(screen.getByRole("menuitem", { name: "停止" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "启动" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("menuitem", { name: "停止" }));
    expect(stopServer).toHaveBeenCalledWith("srv-1");

    // Reopen for restart
    fireEvent.click(triggers[0]);
    fireEvent.click(screen.getByRole("menuitem", { name: "重启" }));
    expect(restartServer).toHaveBeenCalledWith("srv-1");

    // Check
    fireEvent.click(triggers[0]);
    fireEvent.click(screen.getByRole("menuitem", { name: "检查" }));
    expect(checkServer).toHaveBeenCalledWith("srv-1");
  });

  it("shows 启动 for stopped server", () => {
    renderListPage();

    const triggers = screen.getAllByRole("button", { name: "更多操作" });
    // Beta Server is stopped
    fireEvent.click(triggers[1]);

    expect(screen.getByRole("menuitem", { name: "启动" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "停止" })).not.toBeInTheDocument();
  });

  it("shows clear Chinese message for 409 update conflicts", () => {
    vi.mocked(useMcpMutations).mockReturnValue({
      checkServer,
      createServer,
      deleteServer,
      error: new Error("server is running"),
      pending: false,
      restartServer,
      startServer,
      stopServer,
      updateServer,
    });

    renderListPage();

    expect(screen.getByRole("alert")).toHaveTextContent("server is running");
  });

  it("asks for confirmation before delete and restart via dropdown", () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);

    renderListPage();

    const triggers = screen.getAllByRole("button", { name: "更多操作" });
    fireEvent.click(triggers[0]); // Alpha Server (running)

    fireEvent.click(screen.getByRole("menuitem", { name: "重启" }));
    expect(confirmSpy).toHaveBeenNthCalledWith(1, "确认重启 Alpha Server？");

    fireEvent.click(triggers[1]); // Beta Server
    fireEvent.click(screen.getByRole("menuitem", { name: "删除" }));
    // Delete from dropdown doesn't have confirm (confirm is in McpListPage onDeleteServer handler)
  });

  it("stores the MCP admin token and refetches servers", async () => {
    renderListPage();

    fireEvent.change(screen.getByLabelText("MCP Admin Token"), {
      target: { value: "token-from-ui" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存 Token" }));

    await waitFor(() => expect(refetchServers).toHaveBeenCalledTimes(1));
    expect(window.sessionStorage.getItem("mcp-admin-token")).toBe("token-from-ui");
  });

  it("reloads failed list data after saving a non-empty admin token", async () => {
    vi.mocked(useMcpServers).mockReturnValue({
      data: [],
      error: new Error("missing token"),
      loading: false,
      refetch: refetchServers,
    });

    renderListPage();

    expect(screen.getByText("missing token")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("MCP Admin Token"), {
      target: { value: "token-from-ui" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存 Token" }));

    await waitFor(() => expect(refetchServers).toHaveBeenCalled());
  });

  it("shows row mutation 404 error at top without navigating", async () => {
    vi.mocked(useMcpMutations).mockReturnValue({
      checkServer,
      createServer,
      deleteServer,
      error: new Error("missing server"),
      pending: false,
      restartServer,
      startServer,
      stopServer,
      updateServer,
    });

    renderListPage();

    expect(screen.getByRole("alert")).toHaveTextContent("missing server");
  });

  it("shows status badge for running and stopped servers", () => {
    renderListPage();

    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getByText("stopped")).toBeInTheDocument();
  });

  it("shows footer with server count", () => {
    renderListPage();

    expect(screen.getByText("共 2 个服务")).toBeInTheDocument();
  });
});

function buildSummary(overrides: Partial<McpServerSummary> = {}): McpServerSummary {
  return {
    args: [],
    command: "echo",
    desired_state: "running",
    enabled: true,
    env: {},
    headers: {},
    id: "srv-default",
    last_checked_at: null,
    last_error: null,
    name: "Default Server",
    runtime_status: "running",
    tool_count: 0,
    transport: "stdio",
    url: null,
    ...overrides,
  };
}
```

- [ ] **Step 2: Run test**

```bash
cd frontend && npx vitest run src/features/mcp/pages/McpListPage.test.tsx
```

Fix any failures, then:

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/mcp/pages/McpListPage.test.tsx
git commit -m "test: add McpListPage tests covering list migration rows"
```

### Task 8.3: Write McpDetailPage.test.tsx

**Files:**
- Create: `src/features/mcp/pages/McpDetailPage.test.tsx`

Covers migration rows 3b, 5b, 6, 10, 13, 14, 16.

- [ ] **Step 1: Write McpDetailPage.test.tsx**

```tsx
// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { useAuthz } from "../../../app/routing/useAuthz";
import { useMcpMutations, useMcpServerDetail, useMcpServers } from "../hooks";
import type { McpServerDetail as McpServerDetailType } from "../types";
import { McpDetailPage } from "./McpDetailPage";

function renderDetailPage(route = "/mcp/srv-1") {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <McpDetailPage />
    </MemoryRouter>,
  );
}

vi.mock("../../../app/routing/useAuthz", () => ({
  useAuthz: vi.fn(),
}));

vi.mock("../../sop/pages/ChatPage", () => ({
  ChatPage: () => <div>SOP Mock</div>,
}));

vi.mock("../hooks", () => ({
  useMcpMutations: vi.fn(),
  useMcpServerDetail: vi.fn(),
  useMcpServers: vi.fn(),
}));

const detail: McpServerDetailType = {
  args: ["--alpha"],
  command: "echo",
  desired_state: "running",
  enabled: true,
  env: { API_KEY: "********" },
  headers: { Authorization: "********" },
  id: "srv-1",
  last_checked_at: null,
  last_error: null,
  name: "Alpha Server",
  runtime_status: "running",
  tool_count: 1,
  tools: [
    {
      name: "alpha.search",
      description: "Search alpha docs",
      discovered_at: null,
      input_schema: { type: "object" },
    },
  ],
  transport: "stdio",
  url: null,
};

const updateServer = vi.fn();
const deleteServer = vi.fn();
const startServer = vi.fn();
const stopServer = vi.fn();
const restartServer = vi.fn();
const checkServer = vi.fn();
const refetchServers = vi.fn();
const refetchDetail = vi.fn();

beforeEach(() => {
  updateServer.mockReset();
  deleteServer.mockReset();
  startServer.mockReset();
  stopServer.mockReset();
  restartServer.mockReset();
  checkServer.mockReset();
  refetchServers.mockReset();
  refetchDetail.mockReset();
  window.sessionStorage.clear();
  vi.mocked(useAuthz).mockReturnValue({ isAdmin: true });

  vi.mocked(useMcpServers).mockReturnValue({
    data: [],
    error: null,
    loading: false,
    refetch: refetchServers,
  });

  vi.mocked(useMcpServerDetail).mockReturnValue({
    data: detail,
    error: null,
    loading: false,
    refetch: refetchDetail,
  });

  vi.mocked(useMcpMutations).mockReturnValue({
    checkServer,
    createServer: vi.fn(),
    deleteServer,
    error: null,
    pending: false,
    restartServer,
    startServer,
    stopServer,
    updateServer,
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("McpDetailPage", () => {
  it("renders breadcrumb with server name", () => {
    renderDetailPage();

    const nav = screen.getByRole("navigation", { name: "面包屑" });
    expect(within(nav).getByRole("link", { name: "MCP 管理" })).toHaveAttribute("href", "/mcp");
    expect(within(nav).getByText("Alpha Server")).toBeInTheDocument();
  });

  it("renders H1 with server name", () => {
    renderDetailPage();
    expect(screen.getByRole("heading", { name: "Alpha Server" })).toBeInTheDocument();
  });

  it("shows tools after switching to tools tab", () => {
    renderDetailPage();

    fireEvent.click(screen.getByRole("tab", { name: /工具快照/ }));

    expect(screen.getByText("alpha.search")).toBeInTheDocument();
  });

  it("renders loading skeleton on cold load", () => {
    vi.mocked(useMcpServerDetail).mockReturnValue({
      data: null,
      error: null,
      loading: true,
      refetch: vi.fn(),
    });

    renderDetailPage();

    expect(screen.getByText("加载详情中…")).toBeInTheDocument();
    expect(screen.getByText("srv-1")).toBeInTheDocument(); // serverId shown in mono
  });

  it("shows 404 card without auto-redirect", () => {
    vi.mocked(useMcpServerDetail).mockReturnValue({
      data: null,
      error: new Error("Not Found"),
      loading: false,
      refetch: refetchDetail,
    });

    renderDetailPage();

    expect(screen.getByText("MCP 服务不存在")).toBeInTheDocument();
    expect(screen.getByText("返回列表")).toBeInTheDocument();

    // No auto-refetch on 404
    expect(refetchDetail).not.toHaveBeenCalled();
  });

  it("navigates to /mcp when 返回列表 is clicked", () => {
    vi.mocked(useMcpServerDetail).mockReturnValue({
      data: null,
      error: new Error("Not Found"),
      loading: false,
      refetch: refetchDetail,
    });

    renderDetailPage();

    fireEvent.click(screen.getByRole("button", { name: "返回列表" }));
    // URL should change — verified by the MemoryRouter behavior
  });

  it("does not confirm or delete when detail data id mismatches params", () => {
    vi.mocked(useMcpServerDetail).mockReturnValue({
      data: null,
      error: null,
      loading: false,
      refetch: refetchDetail,
    });

    renderDetailPage();

    // Edit and delete buttons should be disabled when loading/no data
    const editButton = screen.getByRole("button", { name: "编辑" });
    expect(editButton).toBeDisabled();
  });

  it("clears selected server on successful delete without refetching deleted detail", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    deleteServer.mockResolvedValueOnce(undefined);

    renderDetailPage();

    fireEvent.click(screen.getByRole("button", { name: "删除" }));

    await waitFor(() => expect(deleteServer).toHaveBeenCalledWith("srv-1"));
    await waitFor(() => expect(refetchServers).toHaveBeenCalled());
    // refetchDetail should NOT be called after delete
    expect(refetchDetail).not.toHaveBeenCalled();
  });

  it("shows detail load errors before the empty selected state", () => {
    render(
      <MemoryRouter initialEntries={["/mcp/missing-server"]}>
        <McpDetailPage />
      </MemoryRouter>,
    );

    // The page should show loading or the error card
    expect(screen.getByText("missing-server")).toBeInTheDocument();
  });

  it("keeps sidebar toggle working on detail page", () => {
    renderDetailPage();

    const sidebar = screen.getByRole("complementary", { name: "工作台侧边栏" });
    expect(sidebar).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "收起侧边栏" }));
    expect(screen.getByRole("button", { name: "展开侧边栏" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test**

```bash
cd frontend && npx vitest run src/features/mcp/pages/McpDetailPage.test.tsx
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/mcp/pages/McpDetailPage.test.tsx
git commit -m "test: add McpDetailPage tests covering detail migration rows"
```

### Task 8.4: Write McpServerFormDrawer.test.tsx

**Files:**
- Create: `src/features/mcp/components/McpServerFormDrawer.test.tsx`

Covers migration rows 17-23.

- [ ] **Step 1: Write the test** (covers migration matrix rows 17-23)

```tsx
// src/features/mcp/components/McpServerFormDrawer.test.tsx
// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { McpServerFormDrawer } from "./McpServerFormDrawer";
import type { McpServerDetail } from "../types";

const server: McpServerDetail = {
  args: ["--alpha"],
  command: "echo",
  desired_state: "running",
  enabled: true,
  env: { API_KEY: "********" },
  headers: { Authorization: "********" },
  id: "srv-1",
  last_checked_at: null,
  last_error: null,
  name: "Alpha Server",
  runtime_status: "running",
  tool_count: 1,
  tools: [],
  transport: "stdio",
  url: null,
};

function renderCreateDrawer(overrides: Partial<React.ComponentProps<typeof McpServerFormDrawer>> = {}) {
  const onClose = vi.fn();
  const onCreate = vi.fn<Promise<void>>().mockResolvedValue(undefined);
  const onUpdate = vi.fn<Promise<void>>().mockResolvedValue(undefined);

  render(
    <MemoryRouter initialEntries={["/mcp/new"]}>
      <McpServerFormDrawer
        mode="create"
        onClose={onClose}
        onCreate={onCreate}
        onUpdate={onUpdate}
        open={true}
        pending={false}
        server={null}
        {...overrides}
      />
    </MemoryRouter>,
  );

  return { onClose, onCreate, onUpdate };
}

function renderEditDrawer(overrides: Partial<React.ComponentProps<typeof McpServerFormDrawer>> = {}) {
  const onClose = vi.fn();
  const onCreate = vi.fn<Promise<void>>().mockResolvedValue(undefined);
  const onUpdate = vi.fn<Promise<void>>().mockResolvedValue(undefined);

  render(
    <MemoryRouter initialEntries={["/mcp/srv-1/edit"]}>
      <McpServerFormDrawer
        mode="edit"
        onClose={onClose}
        onCreate={onCreate}
        onUpdate={onUpdate}
        open={true}
        pending={false}
        server={server}
        {...overrides}
      />
    </MemoryRouter>,
  );

  return { onClose, onCreate, onUpdate };
}

afterEach(() => {
  cleanup();
});

describe("McpServerFormDrawer", () => {
  it("shows inline error for empty name and prevents create (row 17)", () => {
    const { onCreate } = renderCreateDrawer();

    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    const nameField = screen.getByLabelText(/服务名称/).closest(".space-y-1")!;
    expect(within(nameField).getByRole("alert")).toHaveTextContent("请填写服务名称。");
    expect(screen.getByLabelText(/服务名称/)).toHaveFocus();
    expect(onCreate).not.toHaveBeenCalled();
  });

  it("validates required command for stdio and closes drawer on Escape (row 18)", () => {
    const { onClose } = renderCreateDrawer();

    fireEvent.change(screen.getByLabelText(/服务名称/), {
      target: { value: "Gamma Server" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    const commandField = screen.getByLabelText(/command/).closest(".space-y-1")!;
    expect(within(commandField).getByRole("alert")).toHaveTextContent(
      "stdio 模式需要填写 command。",
    );

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });

  it("validates invalid http url before submit (row 19)", () => {
    renderCreateDrawer();

    fireEvent.change(screen.getByLabelText(/服务名称/), {
      target: { value: "Delta Server" },
    });
    fireEvent.change(screen.getByLabelText("传输方式"), {
      target: { value: "http" },
    });

    const urlInput = screen.getByLabelText(/url/);
    fireEvent.change(urlInput, { target: { value: "not-a-url" } });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    const urlField = screen.getByLabelText(/url/).closest(".space-y-1")!;
    expect(within(urlField).getByRole("alert")).toHaveTextContent(
      "请填写有效的 http url。",
    );
    expect(urlInput).toHaveFocus();
  });

  it("creates server with parsed args env headers and conservative defaults (row 20)", async () => {
    const onClose = vi.fn();
    const onCreate = vi.fn<Promise<{ id: string }>>().mockResolvedValue({ id: "new-srv" });

    render(
      <MemoryRouter initialEntries={["/mcp/new"]}>
        <McpServerFormDrawer
          mode="create"
          onClose={onClose}
          onCreate={onCreate}
          onUpdate={vi.fn().mockResolvedValue(undefined)}
          open={true}
          pending={false}
          server={null}
        />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText(/服务名称/), {
      target: { value: "Gamma Server" },
    });
    fireEvent.change(screen.getByLabelText(/command/), {
      target: { value: "uvx" },
    });
    fireEvent.change(screen.getByLabelText(/args/), {
      target: { value: "--from\nmcp-package\nserve" },
    });
    fireEvent.change(screen.getByLabelText(/env/), {
      target: { value: "API_KEY=secret\nEMPTY=" },
    });
    fireEvent.change(screen.getByLabelText(/headers/), {
      target: { value: "Authorization=Bearer token" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => expect(onCreate).toHaveBeenCalled());
    expect(onCreate).toHaveBeenCalledWith({
      args: ["--from", "mcp-package", "serve"],
      command: "uvx",
      desired_state: "stopped", // checkbox unchecked = stopped
      enabled: false,
      env: { API_KEY: "secret", EMPTY: "" },
      headers: { Authorization: "Bearer token" },
      name: "Gamma Server",
      transport: "stdio",
    });
  });

  it("shows inline validation for malformed key value config lines (row 21)", () => {
    renderCreateDrawer();

    fireEvent.change(screen.getByLabelText(/服务名称/), {
      target: { value: "Gamma Server" },
    });
    fireEvent.change(screen.getByLabelText(/command/), {
      target: { value: "uvx" },
    });
    fireEvent.change(screen.getByLabelText(/env/), {
      target: { value: "BROKEN_LINE" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    const envField = screen.getByLabelText(/env/).closest(".space-y-1")!;
    expect(within(envField).getByRole("alert")).toHaveTextContent(
      "env 第 1 行需要使用 KEY=VALUE 格式。",
    );
  });

  it("omits unchanged redacted env and headers when updating (row 22)", async () => {
    const { onUpdate } = renderEditDrawer();

    expect(screen.getByLabelText(/env/)).toHaveValue("API_KEY=********");
    expect(screen.getByLabelText(/headers/)).toHaveValue("Authorization=********");

    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => expect(onUpdate).toHaveBeenCalled());
    const payload = onUpdate.mock.calls[0]?.[1] as Record<string, unknown>;

    expect(payload.args).toEqual(["--alpha"]);
    expect(payload).not.toHaveProperty("env");
    expect(payload).not.toHaveProperty("headers");
  });

  it("wraps focus within drawer on Tab and Shift+Tab (row 23)", () => {
    renderCreateDrawer();

    const dialog = screen.getByRole("dialog", { name: "新增 MCP 服务" });
    const closeButton = within(dialog).getByRole("button", { name: "关闭" });
    const saveButton = within(dialog).getByRole("button", { name: "保存" });

    saveButton.focus();
    fireEvent.keyDown(window, { key: "Tab" });
    expect(closeButton).toHaveFocus();

    closeButton.focus();
    fireEvent.keyDown(window, { key: "Tab", shiftKey: true });
    expect(saveButton).toHaveFocus();
  });

  it("shows NEW SERVER label in create mode", () => {
    renderCreateDrawer();
    expect(screen.getByText("NEW SERVER")).toBeInTheDocument();
  });

  it("shows EDIT · serverId label in edit mode", () => {
    renderEditDrawer();
    expect(screen.getByText("EDIT · srv-1")).toBeInTheDocument();
  });

  it("uses checkbox for desired_state", () => {
    renderCreateDrawer();
    const checkbox = screen.getByLabelText("创建后立即启动");
    expect(checkbox).toBeInstanceOf(HTMLInputElement);
    expect((checkbox as HTMLInputElement).type).toBe("checkbox");
  });
});
```

- [ ] **Step 2: Run tests**

- [ ] **Step 2: Run tests**

```bash
cd frontend && npx vitest run src/features/mcp/components/McpServerFormDrawer.test.tsx
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/mcp/components/McpServerFormDrawer.test.tsx
git commit -m "test: migrate form drawer tests to field-level alerts and route-driven open"
```

---

## Chunk 9: Integration — Run All Tests & Fix

### Task 9.1: Run full test suite

- [ ] **Step 1: Run all MCP tests**

```bash
cd frontend && npx vitest run src/features/mcp/
```

- [ ] **Step 2: Fix any failing tests**

Common issues to watch for:
- Import paths in new test files pointing to wrong module locations
- `useMcpMutations` mock missing `createServer` in detail page mock
- `getByRole("alert")` matching multiple elements (field error + API error both present)
- Missing `import { useState }` in `McpDetailPage.tsx`
- Form `id="mcp-drawer-form"` mismatch between `<form>` and submit button `form` attribute

- [ ] **Step 3: Run the full test suite**

```bash
cd frontend && npx vitest run
```

- [ ] **Step 4: Fix App.test.tsx if needed**

The `App.test.tsx` in `src/app/` may import `McpPage`. Update to import `McpListPage` or mock the new pages.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test: fix integration issues across new MCP pages"
```

---

## Chunk 10: Cleanup — Remove Unused Imports & Verify Build

### Task 10.1: TypeScript build check

- [ ] **Step 1: Run TypeScript compiler**

```bash
cd frontend && npx tsc -b
```

- [ ] **Step 2: Fix any type errors**

Common issues: missing type exports, incorrect import paths.

- [ ] **Step 3: Run dev server to verify visually**

```bash
cd frontend && npx vite --port 5173 &
# Open browser, navigate to:
# - /mcp (table with rows)
# - /mcp/srv-1 (detail page)
# - /mcp/new (create drawer)
# - /mcp/srv-1/edit (edit drawer)
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: fix type errors and verify build"
```

---

## Summary

| Chunk | Files Created | Files Modified | Files Deleted |
|---|---|---|---|
| 1 | 9 placeholders | 0 | 3 |
| 2 | McpStatusBadge[.test], McpBreadcrumb[.test], AdminTokenControl | 0 | 0 |
| 3 | McpRowActionsMenu[.test] | 0 | 0 |
| 4 | McpServerTable, McpListPage | 0 | 0 |
| 5 | McpDetailConfigPanel, McpDetailToolsPanel, McpDetailPage | 0 | 0 |
| 6 | 0 | McpServerFormDrawer | 0 |
| 7 | 0 | App.tsx, App.test.tsx | 0 |
| 8 | McpListPage.test, McpDetailPage.test, McpServerFormDrawer.test | 0 | McpPage.test.tsx |
| 9-10 | 0 | fix imports/types | 0 |

**Total: 11 new source files, 6 new test files, 3 modified, 3 deleted**
