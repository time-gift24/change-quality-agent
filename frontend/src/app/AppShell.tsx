import { Outlet } from "react-router-dom";

export function AppShell() {
  return (
    <div className="flex min-h-screen bg-canvas text-ink bg-aurora">
      <Outlet />
    </div>
  );
}
