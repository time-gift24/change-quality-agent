import { Link } from "react-router-dom";
import type { McpServerSummary } from "../types";
import { McpRowActionsMenu } from "./McpRowActionsMenu";
import { McpStatusBadge } from "./McpStatusBadge";
import { getMcpErrorMessage } from "./errorMessages";
import type { McpStatusFilter } from "../pages/McpListPage";

type McpServerTableProps = {
  servers: McpServerSummary[];
  searchText: string;
  statusFilter: McpStatusFilter;
  loading: boolean;
  error: Error | null;
  pending: boolean;
  onSearchTextChange: (next: string) => void;
  onStatusFilterChange: (next: McpStatusFilter) => void;
  onRefresh: () => void;
  onCreateServer: () => void;
  onStartServer: (serverId: string) => void;
  onStopServer: (serverId: string) => void;
  onRestartServer: (serverId: string) => void;
  onCheckServer: (serverId: string) => void;
  onDeleteServer: (serverId: string) => void;
};

export function McpServerTable({
  servers,
  searchText,
  statusFilter,
  loading,
  error,
  pending: _pending,
  onSearchTextChange,
  onStatusFilterChange,
  onRefresh,
  onCreateServer,
  onStartServer,
  onStopServer,
  onRestartServer,
  onCheckServer,
  onDeleteServer,
}: McpServerTableProps) {
  const errorMessage = getMcpErrorMessage(error);

  return (
    <div className="rounded-xl border border-hairline bg-canvas">
      {/* Toolbar */}
      <div className="flex items-center gap-2 border-b border-hairline px-3 py-2">
        <div className="relative flex-1">
          <svg
            aria-hidden="true"
            className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-mute"
            fill="none"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="2"
            viewBox="0 0 24 24"
          >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            aria-label="搜索 MCP 服务"
            className="h-9 w-64 rounded-lg border border-hairline bg-canvas pl-9 pr-3 text-xs text-ink outline-none transition-colors placeholder:text-mute focus:border-primary focus:ring-2 focus:ring-primary/15"
            onChange={(e) => onSearchTextChange(e.target.value)}
            placeholder="按名称搜索…"
            type="search"
            value={searchText}
          />
        </div>

        <select
          aria-label="状态筛选"
          className="h-9 rounded-lg border border-hairline bg-canvas px-3 text-xs text-ink outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15"
          onChange={(e) => onStatusFilterChange(e.target.value as McpStatusFilter)}
          value={statusFilter}
        >
          <option value="all">全部状态</option>
          <option value="running">Running</option>
          <option value="stopped">Stopped</option>
          <option value="error">Error</option>
          <option value="starting">Starting</option>
          <option value="stopping">Stopping</option>
          <option value="unknown">Unknown</option>
        </select>

        <div className="flex-1" />

        <button
          className="h-9 rounded-lg border border-hairline bg-canvas px-3 text-xs text-body transition-colors hover:border-hairline-strong"
          onClick={onRefresh}
          type="button"
        >
          刷新
        </button>

        <button
          aria-label="新增 MCP Server"
          className="h-9 rounded-lg bg-primary px-3 text-xs font-medium text-on-primary transition-colors hover:bg-primary-deep"
          onClick={onCreateServer}
          type="button"
        >
          + 新增 Server
        </button>
      </div>

      {/* Table */}
      <table className="w-full">
        <thead>
          <tr className="border-b border-hairline bg-canvas-soft">
            <th className="h-10 px-3 text-left text-2xs font-medium uppercase tracking-wide text-mute font-mono">
              名称
            </th>
            <th className="hidden h-10 w-[120px] px-3 text-left text-2xs font-medium uppercase tracking-wide text-mute font-mono sm:table-cell">
              状态
            </th>
            <th className="hidden h-10 w-[80px] px-3 text-right text-2xs font-medium uppercase tracking-wide text-mute font-mono sm:table-cell">
              工具
            </th>
            <th className="hidden h-10 w-[160px] px-3 text-left text-2xs font-medium uppercase tracking-wide text-mute font-mono sm:table-cell">
              最近检查
            </th>
            <th className="h-10 w-[56px] px-2 text-center text-2xs font-medium uppercase tracking-wide text-mute font-mono">
              <span className="sr-only">操作</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td className="py-8 text-center text-xs text-mute" colSpan={5}>
                加载中…
              </td>
            </tr>
          ) : errorMessage ? (
            <tr>
              <td className="border border-error-soft bg-canvas px-3 py-2 text-xs text-error-deep" colSpan={5} role="alert">
                {errorMessage}
              </td>
            </tr>
          ) : servers.length === 0 ? (
            <tr>
              <td className="py-12 text-center text-xs text-mute" colSpan={5}>
                暂无 MCP 服务，点击
                <button
                  className="mx-1 font-medium text-primary hover:underline"
                  onClick={onCreateServer}
                  type="button"
                >
                  + 新增 Server
                </button>
                开始添加。
              </td>
            </tr>
          ) : (
            servers.map((server) => (
              <tr
                key={server.id}
                className="border-b border-hairline transition-colors last:border-0 hover:bg-canvas-soft"
              >
                <td className="px-3 py-2.5">
                  <Link
                    className="block rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
                    to={`/mcp/${server.id}`}
                  >
                    <p className="text-sm font-medium text-ink">{server.name}</p>
                    <p className="text-2xs text-mute font-mono">{server.transport}</p>
                  </Link>
                </td>
                <td className="hidden px-3 py-2.5 sm:table-cell">
                  <McpStatusBadge status={server.runtime_status} />
                </td>
                <td className="hidden px-3 py-2.5 text-right sm:table-cell">
                  <span className="text-2xs tabular-nums font-mono text-body">
                    {server.tool_count}
                  </span>
                </td>
                <td className="hidden px-3 py-2.5 sm:table-cell">
                  <span className="text-2xs text-mute">
                    {server.last_checked_at ?? "-"}
                  </span>
                </td>
                <td className="px-2 py-2.5 text-center">
                  <McpRowActionsMenu
                    onCheck={onCheckServer}
                    onDelete={onDeleteServer}
                    onRestart={onRestartServer}
                    onStart={onStartServer}
                    onStop={onStopServer}
                    runtimeStatus={server.runtime_status}
                    serverId={server.id}
                    serverName={server.name}
                  />
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {/* Footer */}
      <div className="flex items-center justify-between border-t border-hairline px-3 py-2 text-2xs text-mute font-mono">
        <span>
          共 {servers.length} 个服务
          {statusFilter !== "all" ? ` · 显示 ${servers.length} 个` : ""}
        </span>
        <span>全部加载</span>
      </div>
    </div>
  );
}
