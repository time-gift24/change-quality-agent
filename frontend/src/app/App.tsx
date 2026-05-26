import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { ChatPage } from "../features/sop/pages/ChatPage";
import { AppShell } from "./AppShell";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />} path="/">
          <Route element={<Navigate replace to="/sop" />} index />
          <Route element={<ChatPage />} path="sop" />
          <Route element={<Navigate replace to="/sop" />} path="*" />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
