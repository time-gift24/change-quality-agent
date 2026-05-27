import { useCallback, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { McpServerRuntimeStatus } from "../types";

import { McpBreadcrumb } from "../components/McpBreadcrumb";
import { McpServerTable } from "../components/McpServerTable";
import { useMcpMutations, useMcpServers } from "../hooks";

export type McpStatusFilter = "all" | McpServerRuntimeStatus;

export function McpListPage() {
  const serversState = useMcpServers();
  const [searchText, setSearchText] = useState("");
  const [statusFilter, setStatusFilter] = useState<McpStatusFilter>("all");
  const navigate = useNavigate();

  const mutations = useMcpMutations();

  const filteredServers = useMemo(() => {
    const query = searchText.trim().toLowerCase();
    return serversState.data.filter((server) => {
      if (statusFilter !== "all" && server.runtime_status !== statusFilter) return false;
      if (query && !server.name.toLowerCase().includes(query)) return false;
      return true;
    });
  }, [searchText, serversState.data, statusFilter]);

  const mutationErrorMessage = (() => {
    const err = mutations.error;
    if (!err) return null;
    if (err instanceof Error) return err.message;
    return String(err);
  })();

  const runMutation = useCallback(
    async (action: () => Promise<unknown>) => {
      try {
        await action();
        await serversState.refetch();
      } catch {
        // error is stored in mutations.error by the hook
      }
    },
    [mutations, serversState],
  );

  function getServerName(serverId: string) {
    return serversState.data.find((s) => s.id === serverId)?.name ?? "这个 MCP Server";
  }

  return (
    <main aria-label="MCP 管理主内容" className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <header className="flex shrink-0 flex-col gap-3 bg-transparent px-4 py-3">
        <McpBreadcrumb items={[{ label: "MCP 管理" }]} />

        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h1 className="text-base font-semibold tracking-tight text-ink">
              MCP 管理
            </h1>
            <p className="mt-0.5 text-xs text-mute">
              管理 MCP server 生命周期与工具快照
            </p>
          </div>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-4 py-3">
        {mutationErrorMessage ? (
          <p
            className="mb-3 rounded-xl border border-error-soft bg-canvas px-3 py-2 text-xs text-error-deep"
            role="alert"
          >
            {mutationErrorMessage}
          </p>
        ) : null}

        <div className="min-h-0 flex-1 overflow-auto">
          <McpServerTable
            error={serversState.error}
            loading={serversState.loading}
            onCreateServer={() => navigate("/mcp/new")}
            onDeleteServer={(id) => {
              if (window.confirm(`确认删除 ${getServerName(id)}？`)) {
                void runMutation(() => mutations.deleteServer(id));
              }
            }}
            onRefresh={() => { void serversState.refetch(); }}
            onRestartServer={(id) => {
              if (window.confirm(`确认重启 ${getServerName(id)}？`)) {
                void runMutation(() => mutations.restartServer(id));
              }
            }}
            onSearchTextChange={setSearchText}
            onStartServer={(id) => { void runMutation(() => mutations.startServer(id)); }}
            onStatusFilterChange={setStatusFilter}
            onStopServer={(id) => { void runMutation(() => mutations.stopServer(id)); }}
            onCheckServer={(id) => { void runMutation(() => mutations.checkServer(id)); }}
            pending={mutations.pending}
            searchText={searchText}
            servers={filteredServers}
            statusFilter={statusFilter}
          />
        </div>
      </div>
    </main>
  );
}
