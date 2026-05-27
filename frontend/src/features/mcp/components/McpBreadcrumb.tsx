import { Link } from "react-router-dom";

export type McpBreadcrumbItem = {
  label: string;
  to?: string;
};

type McpBreadcrumbProps = {
  items?: McpBreadcrumbItem[];
  serverName?: string;
};

export function McpBreadcrumb({ items, serverName }: McpBreadcrumbProps) {
  const resolvedItems = items ?? [
    { label: "MCP 管理", to: "/mcp" },
    { label: serverName ?? "..." },
  ];

  return (
    <nav aria-label="面包屑" className="text-xs">
      <ol className="flex items-center gap-1.5">
        {resolvedItems.map((item, index) => {
          const isCurrent = index === resolvedItems.length - 1;

          return (
            <li className="flex items-center gap-1.5" key={`${item.label}-${index}`}>
              {index > 0 ? <span aria-hidden="true" className="text-mute">/</span> : null}
              {item.to && !isCurrent ? (
                <Link to={item.to} className="text-mute transition-colors hover:text-ink">
                  {item.label}
                </Link>
              ) : (
                <span
                  aria-current={isCurrent ? "page" : undefined}
                  className="inline-block max-w-[16ch] truncate font-medium text-ink sm:max-w-[24ch]"
                >
                  {item.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
