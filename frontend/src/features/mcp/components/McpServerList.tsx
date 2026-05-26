import type { McpServerRuntimeStatus, McpServerSummary } from "../types";
import { getMcpErrorMessage } from "./errorMessages";

export type McpStatusFilter = "all" | McpServerRuntimeStatus;

type McpServerListProps = {
  servers: McpServerSummary[];
  selectedServerId: string | null;
  searchText: string;
  statusFilter: McpStatusFilter;
  loading: boolean;
  error: Error | null;
  pending: boolean;
  onSearchTextChange: (next: string) => void;
  onStatusFilterChange: (next: McpStatusFilter) => void;
  onSelectServer: (serverId: string) => void;
  onCreateServer: () => void;
  onStartServer: (serverId: string) => void;
  onStopServer: (serverId: string) => void;
  onRestartServer: (serverId: string) => void;
  onCheckServer: (serverId: string) => void;
};

export function McpServerList({
  servers,
  selectedServerId,
  searchText,
  statusFilter,
  loading,
  error,
  pending,
  onSearchTextChange,
  onStatusFilterChange,
  onSelectServer,
  onCreateServer,
  onStartServer,
  onStopServer,
  onRestartServer,
  onCheckServer,
}: McpServerListProps) {
  const errorMessage = getMcpErrorMessage(error);

  return (
    <section className="flex h-full min-h-0 flex-col rounded-2xl border border-hairline bg-canvas/90">
      <header className="border-b border-hairline p-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-ink">MCP Servers</h2>
          <button
            className="rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-on-primary transition hover:bg-primary-deep"
            onClick={onCreateServer}
            type="button"
          >
            新增
          </button>
        </div>
        <div className="mt-3 space-y-2">
          <label className="block text-xs text-body" htmlFor="mcp-server-search">
            搜索
          </label>
          <input
            className="w-full rounded-lg border border-hairline bg-canvas px-3 py-2 text-sm outline-none ring-primary focus:ring-1"
            id="mcp-server-search"
            onChange={(event) => onSearchTextChange(event.target.value)}
            placeholder="按服务名搜索"
            type="search"
            value={searchText}
          />
          <label className="block text-xs text-body" htmlFor="mcp-status-filter">
            状态筛选
          </label>
          <select
            className="w-full rounded-lg border border-hairline bg-canvas px-3 py-2 text-sm outline-none ring-primary focus:ring-1"
            id="mcp-status-filter"
            onChange={(event) => onStatusFilterChange(event.target.value as McpStatusFilter)}
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
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {errorMessage ? (
          <p className="rounded-md bg-error-soft px-2 py-1 text-xs text-error-deep" role="alert">
            {errorMessage}
          </p>
        ) : null}
        {loading ? <p className="px-2 py-2 text-xs text-mute">加载中...</p> : null}
        {!loading && servers.length === 0 ? (
          <p className="px-2 py-2 text-xs text-mute">暂无可用服务。</p>
        ) : null}

        <ul aria-label="MCP 服务列表" className="space-y-2" role="list">
          {servers.map((server) => {
            const selected = selectedServerId === server.id;

            return (
              <li
                className={`rounded-xl border px-3 py-2 transition ${
                  selected
                    ? "border-primary bg-primary-soft"
                    : "border-hairline bg-canvas hover:border-hairline-strong"
                }`}
                key={server.id}
              >
                <button
                  aria-label={`选择服务 ${server.name}`}
                  className="w-full text-left"
                  onClick={() => onSelectServer(server.id)}
                  type="button"
                >
                  <p className="truncate text-sm font-medium text-ink">{server.name}</p>
                  <p className="mt-1 text-2xs text-body">
                    {server.runtime_status} · tools {server.tool_count}
                  </p>
                </button>
                <div className="mt-2 grid grid-cols-4 gap-1">
                  <button
                    aria-label={`启动 ${server.name}`}
                    className="rounded-md border border-hairline bg-canvas px-1.5 py-1 text-2xs text-body transition hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={pending}
                    onClick={() => onStartServer(server.id)}
                    type="button"
                  >
                    Start
                  </button>
                  <button
                    aria-label={`停止 ${server.name}`}
                    className="rounded-md border border-hairline bg-canvas px-1.5 py-1 text-2xs text-body transition hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={pending}
                    onClick={() => onStopServer(server.id)}
                    type="button"
                  >
                    Stop
                  </button>
                  <button
                    aria-label={`重启 ${server.name}`}
                    className="rounded-md border border-hairline bg-canvas px-1.5 py-1 text-2xs text-body transition hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
                    onClick={() => onRestartServer(server.id)}
                    disabled={pending}
                    type="button"
                  >
                    Restart
                  </button>
                  <button
                    aria-label={`检查 ${server.name}`}
                    className="rounded-md border border-hairline bg-canvas px-1.5 py-1 text-2xs text-body transition hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={pending}
                    onClick={() => onCheckServer(server.id)}
                    type="button"
                  >
                    Check
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
