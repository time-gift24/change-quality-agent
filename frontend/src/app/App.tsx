import { useCallback, useMemo, useState, type ReactNode } from "react";
import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";

import { AuthProvider, useAuth } from "../features/auth/AuthContext";
import { DevUserPicker } from "../features/auth/DevUserPicker";
import { DevUserSwitcher } from "../features/auth/DevUserSwitcher";
import {
  AgentCreatePage,
  AgentEditPage,
} from "../features/agents/pages/AgentFormPage";
import { AgentListPage } from "../features/agents/pages/AgentListPage";
import { LlmProviderDetailPage } from "../features/llmProviders/pages/LlmProviderDetailPage";
import {
  LlmProviderCreatePage,
  LlmProviderEditPage,
} from "../features/llmProviders/pages/LlmProviderFormPage";
import { LlmProviderListPage } from "../features/llmProviders/pages/LlmProviderListPage";
import { McpDetailPage } from "../features/mcp/pages/McpDetailPage";
import { McpListPage } from "../features/mcp/pages/McpListPage";
import { McpCreatePage, McpEditPage } from "../features/mcp/pages/McpServerFormPage";
import { ChatPage } from "../features/sop/pages/ChatPage";
import { RecentSopSidebarPanel } from "./RecentSopSidebarPanel";
import { WorkspaceLayoutProvider } from "./WorkspaceLayoutContext";
import { WorkspaceSidebar } from "./WorkspaceSidebar";
import { ProtectedRoute } from "./routing/ProtectedRoute";
import { useAuthz } from "./routing/useAuthz";
import {
  getVisibleWorkspaceSidebarRoutes,
  getWorkspaceRouteKey,
  workspaceRoutes,
  type WorkspaceRouteKey,
} from "./routing/workspaceRoutes";

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AuthenticatedWorkspace />} path="/">
            <Route element={<Navigate replace to="/sop" />} index />
            <Route element={<ChatPage />} path="sop" />
            <Route element={<ProtectedRoute route={workspaceRoutes.mcp} />}>
              <Route element={<McpListPage />} path="mcp" />
              <Route element={<McpCreatePage />} path="mcp/new" />
              <Route element={<McpEditPage />} path="mcp/:serverId/edit" />
              <Route element={<McpDetailPage />} path="mcp/:serverId" />
            </Route>
            <Route element={<ProtectedRoute route={workspaceRoutes["llm-providers"]} />}>
              <Route element={<LlmProviderListPage />} path="llm-providers" />
              <Route element={<LlmProviderCreatePage />} path="llm-providers/new" />
              <Route element={<LlmProviderEditPage />} path="llm-providers/:providerId/edit" />
              <Route element={<LlmProviderDetailPage />} path="llm-providers/:providerId" />
            </Route>
            <Route element={<ProtectedRoute route={workspaceRoutes.agents} />}>
              <Route element={<AgentListPage />} path="agents" />
              <Route element={<AgentCreatePage />} path="agents/new" />
              <Route element={<AgentEditPage />} path="agents/:agentId/edit" />
            </Route>
            <Route element={<Navigate replace to="/sop" />} path="*" />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

function AuthenticatedWorkspace() {
  const { status } = useAuth();

  if (status === "loading") {
    return <AuthStatus busy message="Loading…" />;
  }

  if (status === "anonymous") {
    if (import.meta.env.DEV) {
      return <DevUserPicker />;
    }

    return <AuthStatus message="Authentication required." />;
  }

  return <WorkspaceFrame />;
}

function AuthStatus({ busy = false, message }: { busy?: boolean; message: string }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-aurora px-4 text-sm text-body">
      <p aria-busy={busy} role={busy ? "status" : undefined}>
        {message}
      </p>
    </main>
  );
}

function WorkspaceFrame() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [newConversationHandler, setNewConversationHandler] = useState<(() => void) | null>(null);
  const [sidebarContent, setSidebarContent] = useState<ReactNode | null>(null);
  const [recentRefreshKey, setRecentRefreshKey] = useState(0);
  const navigate = useNavigate();
  const location = useLocation();
  const authz = useAuthz();
  const activeKey = getWorkspaceRouteKey(location.pathname);
  const navRoutes = useMemo(
    () => getVisibleWorkspaceSidebarRoutes(authz),
    [authz],
  );
  const registerNewConversationHandler = useCallback((handler: (() => void) | null) => {
    setNewConversationHandler(() => handler);
  }, []);

  const layoutContext = useMemo(
    () => ({
      refreshRecentSopQualityChecks: () =>
        setRecentRefreshKey((value) => value + 1),
      setNewConversationHandler: registerNewConversationHandler,
      setSidebarContent,
    }),
    [registerNewConversationHandler],
  );

  function handleNewConversation() {
    if (activeKey === "sop" && newConversationHandler) {
      newConversationHandler();
      return;
    }

    navigate("/sop");
  }

  function handleNavigate(routeKey: WorkspaceRouteKey) {
    navigate(workspaceRoutes[routeKey].path);
  }

  return (
    <WorkspaceLayoutProvider value={layoutContext}>
      <div className="flex h-screen overflow-hidden bg-canvas text-ink bg-aurora">
        <WorkspaceSidebar
          activeKey={activeKey}
          navRoutes={navRoutes}
          onNavigate={handleNavigate}
          onNewConversation={handleNewConversation}
          onToggle={() => setSidebarOpen((value) => !value)}
          open={sidebarOpen}
          topContent={import.meta.env.DEV ? <DevUserSwitcher /> : null}
        >
          {sidebarContent ?? (
            <RecentSopSidebarPanel refreshKey={recentRefreshKey} />
          )}
        </WorkspaceSidebar>

        <div className="flex h-screen min-w-0 flex-1 flex-col overflow-hidden">
          <Outlet />
        </div>
      </div>
    </WorkspaceLayoutProvider>
  );
}
