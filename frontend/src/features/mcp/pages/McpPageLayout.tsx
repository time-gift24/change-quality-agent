import type { ReactNode } from "react";

import { McpBreadcrumb, type McpBreadcrumbItem } from "../components/McpBreadcrumb";

type McpPageLayoutProps = {
  actions?: ReactNode;
  children: ReactNode;
  description?: ReactNode;
  items: McpBreadcrumbItem[];
  title: string;
};

export function McpPageLayout({
  actions,
  children,
  description,
  items,
  title,
}: McpPageLayoutProps) {
  return (
    <main aria-label="MCP 管理主内容" className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <header className="flex shrink-0 flex-col gap-3 bg-transparent px-4 py-3">
        <McpBreadcrumb items={items} />

        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h1 className="text-base font-semibold tracking-tight text-ink">
              {title}
            </h1>
            {description ? (
              <div className="mt-0.5 text-xs text-mute">{description}</div>
            ) : null}
          </div>
          {actions ? <div className="flex shrink-0 items-center gap-1.5">{actions}</div> : null}
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {children}
      </div>
    </main>
  );
}
