import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { McpPage } from "../features/mcp/pages/McpPage";
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
            <Route element={<McpPage />} path="mcp" />
          </Route>
          <Route element={<Navigate replace to="/sop" />} path="*" />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
