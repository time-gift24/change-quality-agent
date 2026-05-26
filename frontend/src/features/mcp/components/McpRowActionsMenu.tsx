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
  const initialFocusRef = useRef<"first" | "last">("first");
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

  // Focus first/last item after menu opens (works in both browser and jsdom)
  useEffect(() => {
    if (!open) return;
    const visible = items.filter((i) => !i.separator);
    const idx = initialFocusRef.current === "last" ? visible.length - 1 : 0;
    focusItem(idx);
  }, [open, items, focusItem]);

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
      initialFocusRef.current = "first";
      setOpen(true);
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      initialFocusRef.current = "last";
      setOpen(true);
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
      const el = document.activeElement as HTMLElement | null;
      const currentIdx = visible.findIndex((i) => i.id === el?.dataset?.menuitemId);
      focusItem(currentIdx + 1);
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      const el = document.activeElement as HTMLElement | null;
      const currentIdx = visible.findIndex((i) => i.id === el?.dataset?.menuitemId);
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
        onClick={() => { initialFocusRef.current = "first"; setOpen(true); }}
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
