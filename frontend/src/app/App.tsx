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
            <Route element={<McpListPage />} path="mcp" />
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
