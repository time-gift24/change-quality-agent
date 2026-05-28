import type { ReactNode } from "react";
import { Link } from "react-router-dom";

type BreadcrumbItem = {
  label: string;
  to?: string;
};

type LlmProviderPageLayoutProps = {
  actions?: ReactNode;
  children: ReactNode;
  description?: ReactNode;
  items: BreadcrumbItem[];
  title: string;
};

export function LlmProviderPageLayout({
  actions,
  children,
  description,
  items,
  title,
}: LlmProviderPageLayoutProps) {
  return (
    <main aria-label="LLM Provider 管理主内容" className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <header className="flex shrink-0 flex-col gap-3 bg-transparent px-4 py-3">
        <nav aria-label="面包屑" className="flex items-center gap-1 text-2xs text-mute">
          {items.map((item, index) => (
            <span className="flex items-center gap-1" key={`${item.label}-${index}`}>
              {index > 0 ? <span aria-hidden="true">/</span> : null}
              {item.to ? (
                <Link className="rounded-full px-1.5 py-1 hover:text-primary-deep" to={item.to}>
                  {item.label}
                </Link>
              ) : (
                <span aria-current="page" className="rounded-full px-1.5 py-1 text-ink">
                  {item.label}
                </span>
              )}
            </span>
          ))}
        </nav>
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
