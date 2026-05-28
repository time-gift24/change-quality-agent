import type { AuthzState } from "./useAuthz";

export type WorkspaceRouteKey = "sop" | "mcp";

export type WorkspaceRouteDefinition = {
  key: WorkspaceRouteKey;
  label: string;
  path: string;
  showInSidebar: boolean;
  requiresAdmin?: boolean;
};

export const workspaceRoutes = {
  sop: {
    key: "sop",
    label: "发起新SOP质检",
    path: "/sop",
    showInSidebar: true,
  },
  mcp: {
    key: "mcp",
    label: "MCP 管理",
    path: "/mcp",
    requiresAdmin: true,
    showInSidebar: true,
  },
} satisfies Record<WorkspaceRouteKey, WorkspaceRouteDefinition>;

export const workspaceSidebarRoutes = [
  workspaceRoutes.sop,
  workspaceRoutes.mcp,
] as const;

export function getWorkspaceRouteKey(pathname: string): WorkspaceRouteKey {
  return pathname.startsWith(workspaceRoutes.mcp.path) ? "mcp" : "sop";
}

export function canAccessWorkspaceRoute(
  route: WorkspaceRouteDefinition,
  authz: AuthzState,
): boolean {
  return !route.requiresAdmin || authz.isAdmin;
}

export function getVisibleWorkspaceSidebarRoutes(
  authz: AuthzState,
): WorkspaceRouteDefinition[] {
  return workspaceSidebarRoutes.filter(
    (route) => route.showInSidebar && canAccessWorkspaceRoute(route, authz),
  );
}
