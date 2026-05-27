import { useCallback, type ReactNode } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

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
  const location = useLocation();
  const navigate = useNavigate();
  const detailState = useMcpServerDetail(serverId ?? null);
  const serversState = useMcpServers();
  const mutations = useMcpMutations();

  const server = detailState.data;
  const is404 = isMcpNotFoundError(detailState.error);
  const isLoading = detailState.loading && !server;
  const targetServerId = server?.id ?? serverId ?? "";
  const mutationErrorMessage = getMcpErrorMessage(mutations.error);
  const notice = getNavigationNotice(location.state);

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
      {notice ? <SuccessNotice message={notice} /> : null}
      {mutationErrorMessage ? <ErrorAlert message={mutationErrorMessage} /> : null}
      {isLoading ? <p className="text-xs text-mute">加载详情中…</p> : null}
      {is404 && !isLoading ? <NotFoundState onBack={() => navigate("/mcp", { replace: true })} /> : null}
      {server ? <DetailContent server={server} /> : null}
    </McpPageLayout>
  );
}

function getNavigationNotice(state: unknown): string | null {
  if (!state || typeof state !== "object") return null;
  const maybeNotice = (state as { mcpNotice?: unknown }).mcpNotice;
  return typeof maybeNotice === "string" && maybeNotice.trim()
    ? maybeNotice
    : null;
}

function SuccessNotice({ message }: { message: string }) {
  return (
    <p
      className="mb-3 rounded-xl border border-success/20 bg-success/10 px-3 py-2 text-xs text-success"
      role="status"
    >
      {message}
    </p>
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
    <div className="grid max-w-7xl gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
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

      <aside
        aria-label="配置总览"
        className="space-y-3 xl:sticky xl:top-4 xl:self-start"
      >
        <DetailSummaryCard server={server} />
      </aside>
    </div>
  );
}

function DetailSummaryCard({ server }: { server: McpServerDetail }) {
  const endpointLabel = server.transport === "stdio" ? "command" : "url";
  const endpointValue = server.transport === "stdio" ? server.command : server.url;

  return (
    <div className="overflow-hidden rounded-3xl border border-primary/10 bg-canvas/90 shadow-[0_18px_45px_rgba(0,100,224,0.07)]">
      <div className="border-b border-primary/10 bg-primary-soft/60 px-4 py-3">
        <p className="font-mono text-2xs uppercase tracking-[0.18em] text-primary-deep">
          Server Overview
        </p>
        <h2 className="mt-1 text-sm font-semibold text-ink">配置总览</h2>
        <p className="mt-1 truncate text-xs text-body">{server.name}</p>
      </div>

      <div className="p-4">
        <div className="rounded-2xl border border-hairline bg-canvas-soft/70 px-3 py-3">
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs text-mute">运行状态</span>
            <McpStatusBadge status={server.runtime_status} />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <MetricTile label="Tools" value={String(server.tool_count)} />
            <MetricTile label="Desired" value={server.desired_state} />
          </div>
        </div>

        <dl className="mt-4 space-y-3 text-xs">
          <InfoRow label="服务 ID" value={server.id} />
          <InfoRow label="传输方式" value={server.transport} />
          <InfoRow label={endpointLabel} value={endpointValue ?? "-"} />
          <InfoRow label="启用状态" value={server.enabled ? "enabled" : "disabled"} />
          <InfoRow label="最近检查" value={server.last_checked_at ?? "-"} />
        </dl>

        {server.last_error ? (
          <p className="mt-4 rounded-2xl border border-error-soft bg-error-soft/45 px-3 py-2 text-xs leading-relaxed text-error-deep">
            {server.last_error}
          </p>
        ) : null}
      </div>
    </div>
  );
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-canvas px-3 py-2 ring-1 ring-primary/10">
      <p className="font-mono text-2xs uppercase tracking-[0.14em] text-mute">{label}</p>
      <p className="mt-1 truncate font-mono text-xs font-semibold text-ink">{value}</p>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="text-mute">{label}</dt>
      <dd className="min-w-0 break-all text-right font-mono text-2xs text-ink">{value}</dd>
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
