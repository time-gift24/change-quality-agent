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
import { McpDetailPage } from "../features/mcp/pages/McpDetailPage";
import { McpListPage } from "../features/mcp/pages/McpListPage";
import { McpCreatePage, McpEditPage } from "../features/mcp/pages/McpServerFormPage";
import { ChatPage } from "../features/sop/pages/ChatPage";
import { RecentSopSidebarPanel } from "./RecentSopSidebarPanel";
import { WorkspaceLayoutProvider } from "./WorkspaceLayoutContext";
import { WorkspaceSidebar } from "./WorkspaceSidebar";
import { ProtectedRoute } from "./routing/ProtectedRoute";

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AuthenticatedWorkspace />} path="/">
            <Route element={<Navigate replace to="/sop" />} index />
            <Route element={<ChatPage />} path="sop" />
            <Route element={<ProtectedRoute />}>
              <Route element={<McpListPage />} path="mcp" />
              <Route element={<McpCreatePage />} path="mcp/new" />
              <Route element={<McpEditPage />} path="mcp/:serverId/edit" />
              <Route element={<McpDetailPage />} path="mcp/:serverId" />
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
  const activeKey = location.pathname.startsWith("/mcp") ? "mcp" : "sop";
  const registerNewConversationHandler = useCallback((handler: (() => void) | null) => {
    setNewConversationHandler(() => handler);
  }, []);

  const layoutContext = useMemo(
    () => ({
      refreshRecentSopRuns: () => setRecentRefreshKey((value) => value + 1),
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

  return (
    <WorkspaceLayoutProvider value={layoutContext}>
      <div className="flex h-screen overflow-hidden bg-canvas text-ink bg-aurora">
        <WorkspaceSidebar
          activeKey={activeKey}
          onNavigateMcp={() => navigate("/mcp")}
          onNavigateSop={() => navigate("/sop")}
          onNewConversation={handleNewConversation}
          onToggle={() => setSidebarOpen((value) => !value)}
          open={sidebarOpen}
        >
          {sidebarContent ?? <RecentSopSidebarPanel refreshKey={recentRefreshKey} />}
        </WorkspaceSidebar>

        <div className="flex h-screen min-w-0 flex-1 flex-col overflow-hidden">
          <Outlet />
        </div>
      </div>
    </WorkspaceLayoutProvider>
  );
}
