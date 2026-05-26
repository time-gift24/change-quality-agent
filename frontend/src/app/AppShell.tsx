import { NavLink, Outlet } from "react-router-dom";

const navItemClassName = ({ isActive }: { isActive: boolean }) =>
  `rounded px-3 py-2 text-sm transition ${
    isActive
      ? "bg-primary-soft font-medium text-primary-deep"
      : "text-body hover:bg-canvas-soft hover:text-ink"
  }`;

export function AppShell() {
  return (
    <div className="flex min-h-screen bg-canvas text-ink">
      <aside className="w-56 border-r border-hairline bg-canvas/80 p-4">
        <nav className="flex flex-col gap-2">
          <NavLink className={navItemClassName} to="/sop">
            质量检查
          </NavLink>
          <NavLink className={navItemClassName} to="/mcp">
            MCP 管理
          </NavLink>
        </nav>
      </aside>
      <main className="min-w-0 flex-1">
        <Outlet />
      </main>
    </div>
  );
}
