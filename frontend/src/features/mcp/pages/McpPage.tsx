import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  getMcpErrorMessage,
  isMcpNotFoundError,
} from "../components/errorMessages";
import { getMcpAdminToken, setMcpAdminToken } from "../adminToken";
import { McpServerDetail, type McpDetailTab } from "../components/McpServerDetail";
import { McpServerFormDrawer } from "../components/McpServerFormDrawer";
import { McpServerList, type McpStatusFilter } from "../components/McpServerList";
import { useMcpMutations, useMcpServerDetail, useMcpServers } from "../hooks";
import type { McpServerCreate, McpServerUpdate } from "../types";

type MutationFailure = {
  error: Error;
  serverId: string | null;
};

export function McpPage() {
  const serversState = useMcpServers();
  const [selectedServerId, setSelectedServerId] = useState<string | null>(null);
  const [searchText, setSearchText] = useState("");
  const [statusFilter, setStatusFilter] = useState<McpStatusFilter>("all");
  const [activeTab, setActiveTab] = useState<McpDetailTab>("configuration");
  const [drawerMode, setDrawerMode] = useState<"create" | "edit" | null>(null);
  const [mutationFailure, setMutationFailure] = useState<MutationFailure | null>(null);
  const [adminTokenInput, setAdminTokenInput] = useState(() => getMcpAdminToken());
  const [adminTokenSaved, setAdminTokenSaved] = useState(false);
  const hasAutoSelectedServerRef = useRef(false);

  useEffect(() => {
    if (serversState.data.length === 0) {
      setSelectedServerId(null);
      hasAutoSelectedServerRef.current = false;
      return;
    }

    if (selectedServerId) {
      const exists = serversState.data.some((server) => server.id === selectedServerId);

      if (!exists) {
        setSelectedServerId(serversState.data[0]?.id ?? null);
      }

      return;
    }

    if (!hasAutoSelectedServerRef.current) {
      hasAutoSelectedServerRef.current = true;
      setSelectedServerId(serversState.data[0]?.id ?? null);
    }
  }, [selectedServerId, serversState.data]);

  const detailState = useMcpServerDetail(selectedServerId);

  const mutations = useMcpMutations();

  const refreshServerViews = useCallback(
    async (serverId: string | null) => {
      await serversState.refetch();
      if (serverId && selectedServerId === serverId) {
        await detailState.refetch();
      }
    },
    [detailState, selectedServerId, serversState],
  );

  const handleMutationError = useCallback(
    async (error: unknown, serverId: string | null) => {
      const nextError = asError(error);

      setMutationFailure({ error: nextError, serverId });

      if (isMcpNotFoundError(nextError)) {
        await serversState.refetch();

        if (serverId && selectedServerId === serverId) {
          setSelectedServerId(null);
          setActiveTab("configuration");
        }
      }
    },
    [selectedServerId, serversState],
  );

  const runServerMutation = useCallback(
    (serverId: string, action: () => Promise<unknown>) => {
      void (async () => {
        try {
          await action();
          setMutationFailure(null);
          await refreshServerViews(serverId);
        } catch (error) {
          await handleMutationError(error, serverId);
        }
      })();
    },
    [handleMutationError, refreshServerViews],
  );

  useEffect(() => {
    if (selectedServerId && isMcpNotFoundError(detailState.error)) {
      setSelectedServerId(null);
      setActiveTab("configuration");
    }
  }, [detailState.error, selectedServerId]);

  const getServerName = useCallback(
    (serverId: string) =>
      serversState.data.find((server) => server.id === serverId)?.name ??
      "这个 MCP Server",
    [serversState.data],
  );

  const refreshSelectedDetail = useCallback(async () => {
    await serversState.refetch();
    if (selectedServerId) {
      await detailState.refetch();
    }
  }, [detailState, selectedServerId, serversState]);

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

  const detailMatchesSelectedServer =
    selectedServerId !== null && detailState.data?.id === selectedServerId;
  const selectedServer = detailMatchesSelectedServer ? detailState.data : null;
  const detailLoading =
    detailState.loading ||
    Boolean(selectedServerId && detailState.data && !detailMatchesSelectedServer);
  const mutationErrorMessage = getMcpErrorMessage(
    mutationFailure?.error ?? mutations.error,
  );

  async function handleSaveAdminToken(): Promise<void> {
    setMcpAdminToken(adminTokenInput);
    setAdminTokenInput(getMcpAdminToken());
    setAdminTokenSaved(true);

    if (!getMcpAdminToken()) {
      return;
    }

    await serversState.refetch();

    if (selectedServerId) {
      await detailState.refetch();
    }
  }

  async function handleCreate(payload: McpServerCreate): Promise<void> {
    try {
      const created = await mutations.createServer(payload);

      setMutationFailure(null);
      setSelectedServerId(created.id);
      setDrawerMode(null);
      setActiveTab("configuration");
      await serversState.refetch();
    } catch (error) {
      await handleMutationError(error, null);
    }
  }

  async function handleUpdate(
    serverId: string,
    payload: McpServerUpdate,
  ): Promise<void> {
    try {
      await mutations.updateServer(serverId, payload);
      setMutationFailure(null);
      setDrawerMode(null);
      await refreshSelectedDetail();
    } catch (error) {
      await handleMutationError(error, serverId);
    }
  }

  async function handleDeleteServer(): Promise<void> {
    if (!selectedServerId || !selectedServer) {
      return;
    }

    const serverId = selectedServer.id;
    const serverName = selectedServer.name;

    if (!window.confirm(`确认删除 ${serverName}？`)) {
      return;
    }

    try {
      await mutations.deleteServer(serverId);
      setMutationFailure(null);
      setSelectedServerId(null);
      setActiveTab("configuration");
      await serversState.refetch();
    } catch (error) {
      await handleMutationError(error, serverId);
    }
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

      <section
        aria-label="MCP 后端 Token 设置"
        className="mb-3 flex flex-col gap-2 rounded-lg border border-hairline bg-canvas-soft p-3 md:flex-row md:items-end"
      >
        <div className="min-w-0 flex-1">
          <label className="block text-xs text-body" htmlFor="mcp-admin-token">
            MCP Admin Token
          </label>
          <input
            autoComplete="off"
            className="mt-1 w-full rounded-lg border border-hairline bg-canvas px-3 py-2 text-sm outline-none ring-primary focus:ring-1"
            id="mcp-admin-token"
            onChange={(event) => {
              setAdminTokenInput(event.target.value);
              setAdminTokenSaved(false);
            }}
            placeholder="X-MCP-Admin-Token"
            type="password"
            value={adminTokenInput}
          />
          <p className="mt-1 text-xs text-mute">
            仅用于向后端请求发送 token；管理员访问策略仍由路由保护占位实现。
          </p>
        </div>
        <button
          className="rounded-lg border border-hairline bg-canvas px-3 py-2 text-sm text-body transition hover:border-primary hover:text-primary"
          onClick={() => {
            void handleSaveAdminToken();
          }}
          type="button"
        >
          保存 Token
        </button>
        {adminTokenSaved ? (
          <p className="text-xs text-body" role="status">
            已保存到当前会话
          </p>
        ) : null}
      </section>

      {mutationErrorMessage ? (
        <p className="mb-3 rounded-lg bg-error-soft px-3 py-2 text-xs text-error-deep" role="alert">
          {mutationErrorMessage}
        </p>
      ) : null}

      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
        <McpServerList
          error={serversState.error}
          loading={serversState.loading}
          onCheckServer={(serverId) => {
            runServerMutation(serverId, () => mutations.checkServer(serverId));
          }}
          onCreateServer={() => {
            setDrawerMode("create");
          }}
          onRestartServer={(serverId) => {
            if (window.confirm(`确认重启 ${getServerName(serverId)}？`)) {
              runServerMutation(serverId, () => mutations.restartServer(serverId));
            }
          }}
          onSearchTextChange={setSearchText}
          onSelectServer={(serverId) => {
            setSelectedServerId(serverId);
            setActiveTab("configuration");
          }}
          onStartServer={(serverId) => {
            runServerMutation(serverId, () => mutations.startServer(serverId));
          }}
          onStatusFilterChange={setStatusFilter}
          onStopServer={(serverId) => {
            runServerMutation(serverId, () => mutations.stopServer(serverId));
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
          loading={detailLoading}
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

function asError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error));
}
