import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

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
            <Route
              element={<h1 className="text-xl font-semibold">MCP 管理</h1>}
              path="mcp"
            />
          </Route>
          <Route element={<Navigate replace to="/sop" />} path="*" />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
