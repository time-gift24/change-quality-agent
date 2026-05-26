import { useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "../../../components/ui/button";
import { McpRowActionsMenu } from "../components/McpRowActionsMenu";
import { McpServerForm } from "../components/McpServerForm";
import { McpDetailToolsPanel } from "../components/McpDetailToolsPanel";
import { McpStatusBadge } from "../components/McpStatusBadge";
import { getMcpErrorMessage, isMcpNotFoundError } from "../components/errorMessages";
import { useMcpMutations, useMcpServerDetail, useMcpServers } from "../hooks";
import type { McpServerDetail } from "../types";
import { McpPageLayout } from "./McpPageLayout";

export function McpDetailPage() {
  const { serverId } = useParams<{ serverId: string }>();
  const navigate = useNavigate();
  const detailState = useMcpServerDetail(serverId ?? null);
  const serversState = useMcpServers();
  const mutations = useMcpMutations();

  const server = detailState.data;
  const is404 = isMcpNotFoundError(detailState.error);
  const isLoading = detailState.loading && !server;
  const targetServerId = server?.id ?? serverId ?? "";
  const mutationErrorMessage = getMcpErrorMessage(mutations.error);

  const runMutation = useCallback(
    async (action: () => Promise<unknown>) => {
      try {
        await action();
        await Promise.all([serversState.refetch(), detailState.refetch()]);
      } catch (error) {
        if (isMcpNotFoundError(error instanceof Error ? error : new Error(String(error)))) {
          await serversState.refetch();
        } else {
          await Promise.all([serversState.refetch(), detailState.refetch()]);
        }
      }
    },
    [detailState, serversState],
  );

  async function handleDelete() {
    if (!server) return;
    if (!window.confirm(`确认删除 ${server.name}？`)) return;
    await mutations.deleteServer(targetServerId);
    await serversState.refetch();
    navigate("/mcp", { replace: true });
  }

  return (
    <McpPageLayout
      actions={server ? (
        <>
          <Button
            onClick={() => navigate(`/mcp/${targetServerId}/edit`)}
            variant="secondary"
          >
            编辑
          </Button>
          <Button
            disabled={mutations.pending}
            onClick={() => { void handleDelete(); }}
            variant="destructive"
          >
            删除
          </Button>
          <McpRowActionsMenu
            onCheck={(id) => { void runMutation(() => mutations.checkServer(id)); }}
            onDelete={() => { void handleDelete(); }}
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
        </>
      ) : null}
      description={server ? <DetailDescription server={server} /> : "查看 MCP server 配置。"}
      items={[
        { label: "MCP 管理", to: "/mcp" },
        { label: server?.name ?? serverId ?? "...", to: `/mcp/${targetServerId}` },
        { label: "查看" },
      ]}
      title={server?.name ?? serverId ?? "MCP Server"}
    >
      {mutationErrorMessage ? <ErrorAlert message={mutationErrorMessage} /> : null}
      {isLoading ? <p className="text-xs text-mute">加载详情中…</p> : null}
      {is404 && !isLoading ? <NotFoundState onBack={() => navigate("/mcp", { replace: true })} /> : null}
      {server ? <DetailContent server={server} /> : null}
    </McpPageLayout>
  );
}

function DetailDescription({ server }: { server: McpServerDetail }) {
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <McpStatusBadge status={server.runtime_status} />
      <span aria-hidden="true">·</span>
      <span>{server.transport}</span>
      <span aria-hidden="true">·</span>
      <span>desired {server.desired_state}</span>
    </span>
  );
}

function DetailContent({ server }: { server: McpServerDetail }) {
  return (
    <div className="grid max-w-6xl gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
      <div className="min-w-0 space-y-4">
        {server.last_error ? <ErrorAlert message={server.last_error} /> : null}
        <McpServerForm mode="view" server={server} />

        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink">工具快照</h2>
            <span className="font-mono text-2xs text-mute">{server.tool_count} tools</span>
          </div>
          <McpDetailToolsPanel tools={server.tools} />
        </section>
      </div>

      <aside className="space-y-3">
        <div className="rounded-xl border border-hairline bg-canvas px-4 py-3">
          <h2 className="text-xs font-semibold text-ink">运行信息</h2>
          <dl className="mt-3 space-y-2 text-2xs">
            <InfoRow label="服务 ID" value={server.id} />
            <InfoRow label="最近检查" value={server.last_checked_at ?? "-"} />
            <InfoRow label="启用状态" value={server.enabled ? "enabled" : "disabled"} />
          </dl>
        </div>
      </aside>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="text-mute">{label}</dt>
      <dd className="break-all text-right font-mono text-ink">{value}</dd>
    </div>
  );
}

function ErrorAlert({ message }: { message: string }) {
  return (
    <p className="mb-3 rounded-xl border border-error-soft bg-canvas px-3 py-2 text-xs text-error-deep" role="alert">
      {message}
    </p>
  );
}

function NotFoundState({ onBack }: { onBack: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-hairline bg-canvas py-12 text-center">
      <p className="text-xs text-mute">MCP 服务不存在</p>
      <Button
        onClick={onBack}
        variant="secondary"
      >
        返回列表
      </Button>
    </div>
  );
}
