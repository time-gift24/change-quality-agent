import type { ReactNode } from "react";

type WorkspaceSidebarProps = {
  open: boolean;
  onToggle: () => void;
  activeKey: "sop" | "mcp";
  onNavigateSop: () => void;
  onNavigateMcp: () => void;
  onNewConversation?: () => void;
  children?: ReactNode;
};

export function WorkspaceSidebar({
  open,
  onToggle,
  activeKey,
  onNavigateSop,
  onNavigateMcp,
  onNewConversation,
  children,
}: WorkspaceSidebarProps) {
  function handleNewConversation() {
    if (activeKey === "sop") {
      onNewConversation?.();
      return;
    }
    onNavigateSop();
  }

  function handleMcpClick() {
    if (activeKey === "mcp") {
      return;
    }
    onNavigateMcp();
  }

  return (
    <aside
      aria-label="工作台侧边栏"
      className={`flex shrink-0 flex-col border-r border-hairline bg-canvas/60 backdrop-blur-sm transition-[width] duration-200 ${
        open ? "w-64" : "w-14"
      }`}
    >
      <div className="flex h-14 shrink-0 items-center gap-2 px-3">
        <button
          aria-label={open ? "收起侧边栏" : "展开侧边栏"}
          className="flex h-9 w-9 items-center justify-center rounded-full text-mute transition-colors hover:bg-canvas-soft hover:text-ink"
          onClick={onToggle}
          type="button"
        >
          <SidebarIcon />
        </button>
        {open ? (
          <span className="text-base font-semibold tracking-tight text-ink">
            质量检查
          </span>
        ) : null}
      </div>

      <nav aria-label="工作台导航" className="flex flex-col gap-1 px-2 pt-2">
        <SidebarNavButton
          active={activeKey === "sop"}
          aria-label="发起新SOP质检"
          icon={<PencilIcon />}
          label="发起新SOP质检"
          onClick={handleNewConversation}
          open={open}
        />
        <SidebarNavButton
          active={activeKey === "mcp"}
          aria-label="MCP 管理"
          icon={<ServerIcon />}
          label="MCP 管理"
          onClick={handleMcpClick}
          open={open}
        />
      </nav>

      {open ? (
        <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
      ) : (
        <div className="flex-1" />
      )}
    </aside>
  );
}

type SidebarNavButtonProps = {
  active: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
  open: boolean;
  "aria-label": string;
};

function SidebarNavButton({
  active,
  icon,
  label,
  onClick,
  open,
  "aria-label": ariaLabel,
}: SidebarNavButtonProps) {
  const base =
    "flex h-9 items-center gap-2 rounded-xl text-xs font-medium transition-colors";
  const sizing = open ? "w-full px-2" : "w-10 justify-center px-0";
  const visual = active
    ? "bg-canvas text-ink shadow-sm ring-1 ring-primary/30"
    : "text-body hover:bg-canvas-soft hover:text-ink";

  return (
    <button
      aria-current={active ? "page" : undefined}
      aria-label={ariaLabel}
      className={`${base} ${sizing} ${visual}`}
      onClick={onClick}
      title={open ? undefined : label}
      type="button"
    >
      <span
        aria-hidden="true"
        className="flex h-4 w-4 shrink-0 items-center justify-center"
      >
        {icon}
      </span>
      {open ? <span className="truncate">{label}</span> : null}
    </button>
  );
}

function SidebarIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <rect x="3" y="4" width="18" height="16" rx="3" />
      <path d="M9 4v16" />
    </svg>
  );
}

function PencilIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <path d="M16 3l5 5-12 12H4v-5z" />
      <path d="M14 5l5 5" />
    </svg>
  );
}

function ServerIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <rect x="3" y="4" width="18" height="7" rx="2" />
      <rect x="3" y="13" width="18" height="7" rx="2" />
      <path d="M7 7.5h.01M7 16.5h.01" />
    </svg>
  );
}
