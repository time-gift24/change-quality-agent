import { useCallback, useState } from "react";
import { useLocation, useMatch, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { WorkspaceSidebar } from "../../../app/WorkspaceSidebar";
import { McpBreadcrumb } from "../components/McpBreadcrumb";
import { McpDetailConfigPanel } from "../components/McpDetailConfigPanel";
import { McpDetailToolsPanel } from "../components/McpDetailToolsPanel";
import { McpRowActionsMenu } from "../components/McpRowActionsMenu";
import { McpServerFormDrawer } from "../components/McpServerFormDrawer";
import { McpStatusBadge } from "../components/McpStatusBadge";
import { getMcpErrorMessage, isMcpNotFoundError } from "../components/errorMessages";
import { useMcpMutations, useMcpServerDetail, useMcpServers } from "../hooks";

type McpDetailTab = "configuration" | "tools";

export function McpDetailPage() {
  const { serverId } = useParams<{ serverId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();

  const tabParam = searchParams.get("tab");
  const activeTab: McpDetailTab =
    tabParam === "tools" ? "tools" : "configuration";

  const isEditDrawerOpen = useMatch("/mcp/:serverId/edit") !== null;
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const detailState = useMcpServerDetail(serverId ?? null);
  const serversState = useMcpServers();
  const mutations = useMcpMutations();

  const server = detailState.data;
  const is404 = isMcpNotFoundError(detailState.error);
  const isLoading = detailState.loading && !detailState.data;

  const mutationErrorMessage = (() => {
    const err = mutations.error;
    if (!err) return null;
    if (err instanceof Error) return err.message;
    return String(err);
  })();

  const targetServerId = server?.id ?? serverId ?? "";

  const runMutation = useCallback(
    async (action: () => Promise<unknown>) => {
      try {
        await action();
        await Promise.all([serversState.refetch(), detailState.refetch()]);
      } catch (e) {
        if (isMcpNotFoundError(e instanceof Error ? e : new Error(String(e)))) {
          await serversState.refetch();
        } else {
          await serversState.refetch();
          await detailState.refetch();
        }
      }
    },
    [serversState, detailState],
  );

  const show404Card = is404 && !isLoading;

  return (
    <div className="flex min-h-screen flex-1 text-ink">
      <WorkspaceSidebar
        activeKey="mcp"
        onNavigateMcp={() => navigate("/mcp")}
        onNavigateSop={() => navigate("/sop")}
        onToggle={() => setSidebarOpen((v) => !v)}
        open={sidebarOpen}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <main className="flex flex-1 flex-col overflow-hidden">
          {/* Top strip */}
          <div className="flex shrink-0 flex-col gap-3 border-b border-hairline bg-canvas/60 px-4 py-3 backdrop-blur-sm">
            <McpBreadcrumb
              serverName={server?.name ?? serverId ?? "..."}
            />

            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                {isLoading ? (
                  <h1 className="font-mono text-base text-mute">{serverId}</h1>
                ) : is404 ? (
                  <h1 className="font-mono text-base text-mute">{serverId}</h1>
                ) : server ? (
                  <>
                    <h1 className="text-base font-semibold tracking-tight text-ink">
                      {server.name}
                    </h1>
                    <p className="mt-0.5 text-2xs text-mute flex items-center gap-1.5">
                      <McpStatusBadge status={server.runtime_status} />
                      <span aria-hidden="true">·</span>
                      <span>{server.transport}</span>
                      <span aria-hidden="true">·</span>
                      <span>desired {server.desired_state}</span>
                    </p>
                  </>
                ) : null}
              </div>

              <div className="flex shrink-0 items-center gap-1.5">
                <button
                  aria-disabled={isLoading || is404}
                  className="h-9 rounded-lg border border-hairline bg-canvas px-3 text-xs text-body transition-colors hover:border-hairline-strong hover:text-ink aria-disabled:cursor-not-allowed aria-disabled:opacity-50"
                  disabled={isLoading || is404}
                  onClick={() => {
                    if (is404) {
                      navigate("/mcp", { replace: true });
                      return;
                    }
                    navigate({
                      pathname: `/mcp/${targetServerId}/edit`,
                      search: location.search,
                    });
                  }}
                  type="button"
                >
                  编辑
                </button>
                <button
                  aria-disabled={isLoading || is404}
                  className="h-9 rounded-lg border border-error/40 bg-canvas px-3 text-xs font-medium text-error-deep transition-colors hover:bg-error-soft aria-disabled:cursor-not-allowed aria-disabled:opacity-50"
                  disabled={isLoading || is404 || mutations.pending}
                  onClick={() => {
                    if (!server) return;
                    if (!window.confirm(`确认删除 ${server.name}？`)) return;
                    void (async () => {
                      await mutations.deleteServer(targetServerId);
                      await serversState.refetch();
                      navigate("/mcp", { replace: true });
                    })();
                  }}
                  type="button"
                >
                  删除
                </button>
                {server ? (
                  <McpRowActionsMenu
                    onCheck={(id) => { void runMutation(() => mutations.checkServer(id)); }}
                    onDelete={() => {}}
                    onRestart={(id) => {
                      if (window.confirm(`确认重启 ${server.name}？`)) {
                        void runMutation(() => mutations.restartServer(id));
                      }
                    }}
                    onStart={(id) => { void runMutation(() => mutations.startServer(id)); }}
                    onStop={(id) => { void runMutation(() => mutations.stopServer(id)); }}
                    runtimeStatus={server.runtime_status}
                    serverId={targetServerId}
                    serverName={server.name}
                  />
                ) : null}
              </div>
            </div>
          </div>

          {/* Tab bar */}
          <div className="border-b border-hairline px-4" role="tablist">
            <button
              aria-controls="mcp-detail-config-panel"
              aria-selected={activeTab === "configuration"}
              className={`h-9 px-3 text-xs font-medium transition-colors ${
                activeTab === "configuration"
                  ? "text-ink shadow-[inset_0_-2px_0_var(--color-primary)]"
                  : "text-mute hover:text-ink"
              }`}
              onClick={() => setSearchParams({ tab: "configuration" }, { replace: true })}
              role="tab"
              type="button"
            >
              配置
            </button>
            <button
              aria-controls="mcp-detail-tools-panel"
              aria-selected={activeTab === "tools"}
              className={`h-9 px-3 text-xs font-medium transition-colors ${
                activeTab === "tools"
                  ? "text-ink shadow-[inset_0_-2px_0_var(--color-primary)]"
                  : "text-mute hover:text-ink"
              }`}
              onClick={() => setSearchParams({ tab: "tools" }, { replace: true })}
              role="tab"
              type="button"
            >
              工具快照{server ? ` (${server.tool_count})` : ""}
            </button>
          </div>

          {/* Content */}
          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            {mutationErrorMessage ? (
              <p
                className="mb-3 rounded-xl border border-error-soft bg-canvas px-3 py-2 text-xs text-error-deep"
                role="alert"
              >
                {mutationErrorMessage}
              </p>
            ) : null}

            {isLoading ? (
              <p className="text-xs text-mute">加载详情中…</p>
            ) : show404Card ? (
              <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
                <p className="text-xs text-mute">MCP 服务不存在</p>
                <button
                  className="h-9 rounded-lg border border-hairline bg-canvas px-3 text-xs text-body transition-colors hover:border-hairline-strong hover:text-ink"
                  onClick={() => navigate("/mcp", { replace: true })}
                  type="button"
                >
                  返回列表
                </button>
              </div>
            ) : server ? (
              activeTab === "configuration" ? (
                <div
                  id="mcp-detail-config-panel"
                  role="tabpanel"
                >
                  <McpDetailConfigPanel server={server} />
                </div>
              ) : (
                <div
                  id="mcp-detail-tools-panel"
                  role="tabpanel"
                >
                  <McpDetailToolsPanel tools={server.tools} />
                </div>
              )
            ) : null}
          </div>
        </main>
      </div>

      {/* Edit drawer */}
      {server || isEditDrawerOpen ? (
        <McpServerFormDrawer
          mode="edit"
          onClose={() =>
            navigate({
              pathname: `/mcp/${targetServerId}`,
              search: location.search,
            })
          }
          onCreate={async () => {}}
          onUpdate={async (srvId, payload) => {
            try {
              await mutations.updateServer(srvId, payload);
              await Promise.all([serversState.refetch(), detailState.refetch()]);
              navigate({
                pathname: `/mcp/${targetServerId}`,
                search: location.search,
              });
            } catch (e) {
              if (!isMcpNotFoundError(e instanceof Error ? e : new Error(String(e)))) {
                await detailState.refetch();
              }
              await serversState.refetch();
            }
          }}
          open={isEditDrawerOpen}
          pending={mutations.pending}
          server={server}
        />
      ) : null}
    </div>
  );
}
