import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
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
const MENU_WIDTH = 176;
const MENU_GAP = 6;
const VIEWPORT_PADDING = 8;

type MenuPosition = {
  left: number;
  top: number;
};

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
  const [menuPosition, setMenuPosition] = useState<MenuPosition | null>(null);
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

  const calculateMenuPosition = useCallback((): MenuPosition | null => {
    const trigger = triggerRef.current;
    if (!trigger) return null;

    const triggerRect = trigger.getBoundingClientRect();
    const menuHeight = menuRef.current?.offsetHeight ?? 0;
    const maxLeft = window.innerWidth - MENU_WIDTH - VIEWPORT_PADDING;
    const left = Math.max(
      VIEWPORT_PADDING,
      Math.min(triggerRect.right - MENU_WIDTH, maxLeft),
    );
    const hasBottomSpace =
      !menuHeight || triggerRect.bottom + MENU_GAP + menuHeight <= window.innerHeight - VIEWPORT_PADDING;
    const top = hasBottomSpace
      ? triggerRect.bottom + MENU_GAP
      : Math.max(VIEWPORT_PADDING, triggerRect.top - menuHeight - MENU_GAP);

    return { left, top };
  }, []);

  const updateMenuPosition = useCallback(() => {
    const nextPosition = calculateMenuPosition();
    if (nextPosition) setMenuPosition(nextPosition);
  }, [calculateMenuPosition]);

  const openMenu = useCallback((initialFocus: "first" | "last") => {
    initialFocusRef.current = initialFocus;
    const nextPosition = calculateMenuPosition();
    if (nextPosition) setMenuPosition(nextPosition);
    setOpen(true);
  }, [calculateMenuPosition]);

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

  useLayoutEffect(() => {
    if (!open) return;

    updateMenuPosition();
  }, [open, updateMenuPosition]);

  useEffect(() => {
    if (!open) return;

    window.addEventListener("resize", updateMenuPosition);
    window.addEventListener("scroll", updateMenuPosition, true);

    return () => {
      window.removeEventListener("resize", updateMenuPosition);
      window.removeEventListener("scroll", updateMenuPosition, true);
    };
  }, [open, updateMenuPosition]);

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
      openMenu("first");
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      openMenu("last");
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

  const menu = open && menuPosition ? (
    <div
      ref={menuRef}
      aria-labelledby={triggerId}
      className="fixed z-50 w-44 rounded-2xl border border-hairline-soft bg-canvas p-1 shadow-lg shadow-primary/10"
      onKeyDown={handleMenuKeyDown}
      role="menu"
      style={{ left: menuPosition.left, top: menuPosition.top }}
    >
      {items.map((item) =>
        item.separator ? (
          <div key={item.id} className="my-1 border-t border-hairline" role="separator" />
        ) : item.linkTo ? (
          <Link
            key={item.id}
            className="flex items-center rounded-xl px-3 py-2 text-xs text-body transition-colors hover:bg-canvas-soft focus:bg-canvas-soft focus:outline-none"
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
            className={`flex w-full items-center rounded-xl px-3 py-2 text-xs transition-colors hover:bg-canvas-soft focus:bg-canvas-soft focus:outline-none ${
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
  ) : null;

  return (
    <div className="relative inline-block">
      <button
        ref={triggerRef}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="更多操作"
        className="flex h-8 w-8 items-center justify-center rounded-lg text-mute transition-colors hover:bg-canvas-soft hover:text-ink"
        id={triggerId}
        onClick={() => openMenu("first")}
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

      {menu && typeof document !== "undefined" ? createPortal(menu, document.body) : null}
    </div>
  );
}
