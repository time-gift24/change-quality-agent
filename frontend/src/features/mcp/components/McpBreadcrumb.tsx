import { Link } from "react-router-dom";

type McpBreadcrumbProps = {
  serverName: string;
};

export function McpBreadcrumb({ serverName }: McpBreadcrumbProps) {
  return (
    <nav aria-label="面包屑" className="text-2xs font-mono">
      <ol className="flex items-center gap-1.5">
        <li>
          <Link to="/mcp" className="text-mute hover:text-ink transition-colors">
            MCP 管理
          </Link>
        </li>
        <li aria-hidden="true" className="text-mute">›</li>
        <li>
          <span
            aria-current="page"
            className="text-ink font-medium truncate max-w-[16ch] sm:max-w-[24ch] inline-block"
          >
            {serverName}
          </span>
        </li>
      </ol>
    </nav>
  );
}
