import type { ReactNode } from "react";
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
} from "../components/ui/sidebar";
import type {
  WorkspaceRouteDefinition,
  WorkspaceRouteKey,
} from "./routing/workspaceRoutes";

type WorkspaceSidebarProps = {
  open: boolean;
  onToggle: () => void;
  activeKey: WorkspaceRouteKey;
  navRoutes: WorkspaceRouteDefinition[];
  onNavigate: (routeKey: WorkspaceRouteKey) => void;
  onNewConversation?: () => void;
  topContent?: ReactNode;
  children?: ReactNode;
};

export function WorkspaceSidebar({
  open,
  onToggle,
  activeKey,
  navRoutes,
  onNavigate,
  onNewConversation,
  topContent,
  children,
}: WorkspaceSidebarProps) {
  function handleNewConversation() {
    if (activeKey === "sop") {
      onNewConversation?.();
      return;
    }
    onNavigate("sop");
  }

  function handleRouteClick(routeKey: WorkspaceRouteKey) {
    if (routeKey === "sop") {
      handleNewConversation();
      return;
    }
    if (routeKey === activeKey) {
      return;
    }
    onNavigate(routeKey);
  }

  return (
    <Sidebar
      aria-label="工作台侧边栏"
      className={`flex shrink-0 flex-col border-r border-hairline bg-canvas/60 backdrop-blur-sm transition-[width] duration-200 ${
        open ? "w-64" : "w-14"
      }`}
    >
      <SidebarHeader>
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
      </SidebarHeader>

      {open && topContent ? topContent : null}

      <SidebarMenu aria-label="工作台导航">
        {navRoutes.map((route) => (
          <SidebarNavButton
            active={activeKey === route.key}
            aria-label={route.label}
            icon={iconForRoute(route.key)}
            key={route.key}
            label={route.label}
            onClick={() => handleRouteClick(route.key)}
            open={open}
          />
        ))}
      </SidebarMenu>

      {open ? (
        <SidebarContent>{children}</SidebarContent>
      ) : (
        <div className="flex-1" />
      )}
    </Sidebar>
  );
}

function iconForRoute(routeKey: WorkspaceRouteKey) {
  if (routeKey === "sop") return <PencilIcon />;
  if (routeKey === "llm-providers") return <CpuIcon />;
  return <ServerIcon />;
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
  return (
    <SidebarMenuButton
      aria-label={ariaLabel}
      isActive={active}
      onClick={onClick}
      open={open}
      title={open ? undefined : label}
    >
      <span
        aria-hidden="true"
        className="flex h-4 w-4 shrink-0 items-center justify-center"
      >
        {icon}
      </span>
      {open ? <span className="truncate">{label}</span> : null}
    </SidebarMenuButton>
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

function CpuIcon() {
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
      <rect x="6" y="6" width="12" height="12" rx="2" />
      <path d="M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3" />
      <path d="M10 10h4v4h-4z" />
    </svg>
  );
}
