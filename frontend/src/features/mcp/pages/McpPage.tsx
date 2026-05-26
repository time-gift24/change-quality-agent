import { useCallback, useEffect, useMemo, useState } from "react";

import { McpServerDetail, type McpDetailTab } from "../components/McpServerDetail";
import { McpServerFormDrawer } from "../components/McpServerFormDrawer";
import { McpServerList, type McpStatusFilter } from "../components/McpServerList";
import { useMcpMutations, useMcpServerDetail, useMcpServers } from "../hooks";
import type { McpServerCreate, McpServerUpdate } from "../types";

export function McpPage() {
  const serversState = useMcpServers();
  const [selectedServerId, setSelectedServerId] = useState<string | null>(null);
  const [searchText, setSearchText] = useState("");
  const [statusFilter, setStatusFilter] = useState<McpStatusFilter>("all");
  const [activeTab, setActiveTab] = useState<McpDetailTab>("configuration");
  const [drawerMode, setDrawerMode] = useState<"create" | "edit" | null>(null);

  useEffect(() => {
    if (serversState.data.length === 0) {
      setSelectedServerId(null);
      return;
    }

    const exists = selectedServerId
      ? serversState.data.some((server) => server.id === selectedServerId)
      : false;

    if (!exists) {
      setSelectedServerId(serversState.data[0]?.id ?? null);
    }
  }, [selectedServerId, serversState.data]);

  const detailState = useMcpServerDetail(selectedServerId);

  const refreshAll = useCallback(async () => {
    await serversState.refetch();
    if (selectedServerId) {
      await detailState.refetch();
    }
  }, [detailState, selectedServerId, serversState]);

  const mutations = useMcpMutations({
    onSuccess: refreshAll,
  });

  const filteredServers = useMemo(() => {
    const normalizedQuery = searchText.trim().toLowerCase();

    return serversState.data.filter((server) => {
      const matchesStatus =
        statusFilter === "all" || server.runtime_status === statusFilter;
      const matchesSearch =
        normalizedQuery.length === 0 ||
        server.name.toLowerCase().includes(normalizedQuery);

      return matchesStatus && matchesSearch;
    });
  }, [searchText, serversState.data, statusFilter]);

  const selectedServer = detailState.data;

  async function handleCreate(payload: McpServerCreate): Promise<void> {
    const created = await mutations.createServer(payload);
    setSelectedServerId(created.id);
    setDrawerMode(null);
    setActiveTab("configuration");
  }

  async function handleUpdate(
    serverId: string,
    payload: McpServerUpdate,
  ): Promise<void> {
    await mutations.updateServer(serverId, payload);
    setDrawerMode(null);
  }

  async function handleDeleteServer(): Promise<void> {
    if (!selectedServerId) {
      return;
    }

    await mutations.deleteServer(selectedServerId);
    setSelectedServerId(null);
    setActiveTab("configuration");
  }

  return (
    <div className="flex h-full min-h-screen flex-col bg-canvas p-4">
      <header className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink">MCP 管理</h1>
          <p className="mt-1 text-sm text-body">管理 MCP server 生命周期与工具快照。</p>
        </div>
        <button
          className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-on-primary transition hover:bg-primary-deep"
          onClick={() => setDrawerMode("create")}
          type="button"
        >
          新增 MCP Server
        </button>
      </header>

      {mutations.error ? (
        <p className="mb-3 rounded-lg bg-error-soft px-3 py-2 text-xs text-error-deep" role="alert">
          {mutations.error.message}
        </p>
      ) : null}

      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
        <McpServerList
          error={serversState.error}
          loading={serversState.loading}
          onCheckServer={(serverId) => {
            void mutations.checkServer(serverId);
          }}
          onCreateServer={() => {
            setDrawerMode("create");
          }}
          onRestartServer={(serverId) => {
            void mutations.restartServer(serverId);
          }}
          onSearchTextChange={setSearchText}
          onSelectServer={(serverId) => {
            setSelectedServerId(serverId);
            setActiveTab("configuration");
          }}
          onStartServer={(serverId) => {
            void mutations.startServer(serverId);
          }}
          onStatusFilterChange={setStatusFilter}
          onStopServer={(serverId) => {
            void mutations.stopServer(serverId);
          }}
          pending={mutations.pending}
          searchText={searchText}
          selectedServerId={selectedServerId}
          servers={filteredServers}
          statusFilter={statusFilter}
        />

        <McpServerDetail
          activeTab={activeTab}
          error={detailState.error}
          loading={detailState.loading}
          onDeleteServer={() => {
            void handleDeleteServer();
          }}
          onEditServer={() => {
            if (selectedServer) {
              setDrawerMode("edit");
            }
          }}
          onTabChange={setActiveTab}
          pending={mutations.pending}
          server={selectedServer}
        />
      </div>

      <McpServerFormDrawer
        mode={drawerMode ?? "create"}
        onClose={() => setDrawerMode(null)}
        onCreate={handleCreate}
        onUpdate={handleUpdate}
        open={drawerMode !== null}
        pending={mutations.pending}
        server={selectedServer}
      />
    </div>
  );
}
