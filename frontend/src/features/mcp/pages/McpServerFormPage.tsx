import type { ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { McpServerForm } from "../components/McpServerForm";
import { McpStatusBadge } from "../components/McpStatusBadge";
import { getMcpErrorMessage, isMcpNotFoundError } from "../components/errorMessages";
import { useMcpMutations, useMcpServerDetail } from "../hooks";
import type { McpServerDetail } from "../types";
import { McpPageLayout } from "./McpPageLayout";

export function McpCreatePage() {
  const navigate = useNavigate();
  const mutations = useMcpMutations();
  const mutationErrorMessage = getMcpErrorMessage(mutations.error);

  return (
    <McpPageLayout
      items={[{ label: "MCP 管理", to: "/mcp" }, { label: "新增 Server" }]}
      title="新增 MCP Server"
      description="按页面表单创建 MCP server，保存后进入查看页。"
    >
      <FormGrid
        aside={(
          <FormSideNote
            title="保存策略"
            lines={[
              "默认创建为 stopped，避免保存后立刻拉起未知进程。",
              "stdio 需要 command；http 需要完整 http/https url。",
              "env 和 headers 使用 KEY=VALUE，每行一条。",
            ]}
          />
        )}
      >
        {mutationErrorMessage ? <ErrorAlert message={mutationErrorMessage} /> : null}
        <McpServerForm
          mode="create"
          onCancel={() => navigate("/mcp")}
          onCreate={async (payload) => {
            const created = await mutations.createServer(payload);
            navigate(`/mcp/${created.id}`, {
              state: { mcpNotice: "MCP Server 已创建。" },
            });
          }}
          pending={mutations.pending}
          server={null}
        />
      </FormGrid>
    </McpPageLayout>
  );
}

export function McpEditPage() {
  const { serverId } = useParams<{ serverId: string }>();
  const navigate = useNavigate();
  const detailState = useMcpServerDetail(serverId ?? null);
  const mutations = useMcpMutations();
  const server = detailState.data;
  const targetServerId = server?.id ?? serverId ?? "";
  const mutationErrorMessage = getMcpErrorMessage(mutations.error);
  const is404 = isMcpNotFoundError(detailState.error);

  return (
    <McpPageLayout
      items={[
        { label: "MCP 管理", to: "/mcp" },
        { label: server?.name ?? serverId ?? "...", to: `/mcp/${targetServerId}` },
        { label: "编辑" },
      ]}
      title="编辑 MCP Server"
      description={server ? `${server.transport} · 当前 ${server.runtime_status}` : "修改 MCP server 配置。"}
    >
      {detailState.loading && !server ? <LoadingState label="加载编辑表单中…" /> : null}
      {is404 && !detailState.loading ? <NotFoundState /> : null}
      {server ? (
        <FormGrid aside={<ServerSideNote server={server} />}>
          {mutationErrorMessage ? <ErrorAlert message={mutationErrorMessage} /> : null}
          <McpServerForm
            mode="edit"
            onCancel={() => navigate(`/mcp/${targetServerId}`)}
            onUpdate={async (srvId, payload) => {
              await mutations.updateServer(srvId, payload);
              await detailState.refetch();
              navigate(`/mcp/${targetServerId}`, {
                state: { mcpNotice: "MCP Server 配置已保存。" },
              });
            }}
            pending={mutations.pending}
            server={server}
          />
        </FormGrid>
      ) : null}
    </McpPageLayout>
  );
}

function FormGrid({ children, aside }: { children: ReactNode; aside: ReactNode }) {
  return (
    <div className="grid max-w-7xl gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-w-0 space-y-4">{children}</div>
      <aside
        aria-label="配置摘要"
        className="space-y-3 xl:sticky xl:top-4 xl:self-start"
      >
        {aside}
      </aside>
    </div>
  );
}

function FormSideNote({ title, lines }: { title: string; lines: string[] }) {
  return (
    <div className="overflow-hidden rounded-3xl border border-primary/10 bg-canvas/90 shadow-[0_18px_45px_rgba(0,100,224,0.07)]">
      <div className="border-b border-primary/10 bg-primary-soft/60 px-4 py-3">
        <p className="font-mono text-2xs uppercase tracking-[0.18em] text-primary-deep">
          Config Summary
        </p>
        <h2 className="mt-1 text-sm font-semibold text-ink">配置摘要</h2>
        <p className="mt-1 text-xs leading-relaxed text-body">{title}</p>
      </div>
      <ol className="space-y-3 p-4">
        {lines.map((line, index) => (
          <li className="flex gap-3" key={line}>
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-2xs font-semibold text-on-primary">
              {index + 1}
            </span>
            <p className="pt-0.5 text-xs leading-relaxed text-body">{line}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}

function ServerSideNote({ server }: { server: McpServerDetail }) {
  const endpointLabel = server.transport === "stdio" ? "command" : "url";
  const endpointValue = server.transport === "stdio" ? server.command : server.url;

  return (
    <div className="overflow-hidden rounded-3xl border border-primary/10 bg-canvas/90 shadow-[0_18px_45px_rgba(0,100,224,0.07)]">
      <div className="border-b border-primary/10 bg-primary-soft/60 px-4 py-3">
        <p className="font-mono text-2xs uppercase tracking-[0.18em] text-primary-deep">
          Live Config
        </p>
        <h2 className="mt-1 text-sm font-semibold text-ink">配置摘要</h2>
        <p className="mt-1 truncate text-xs text-body">{server.name}</p>
      </div>

      <dl className="space-y-3 p-4 text-xs">
        <SideRow label="运行状态" value={<McpStatusBadge status={server.runtime_status} />} />
        <SideRow label="传输方式" value={server.transport} />
        <SideRow label={endpointLabel} value={endpointValue ?? "-"} />
        <SideRow label="目标状态" value={server.desired_state} />
        <SideRow label="启用状态" value={server.enabled ? "enabled" : "disabled"} />
        <SideRow label="工具数量" value={`${server.tool_count} tools`} />
        <SideRow label="最近检查" value={server.last_checked_at ?? "-"} />
      </dl>

      {server.last_error ? (
        <p className="mx-4 mb-4 rounded-2xl border border-error-soft bg-error-soft/45 px-3 py-2 text-xs leading-relaxed text-error-deep">
          {server.last_error}
        </p>
      ) : null}
    </div>
  );
}

function SideRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="text-mute">{label}</dt>
      <dd className="min-w-0 break-all text-right font-mono text-2xs text-ink">{value}</dd>
    </div>
  );
}

function ErrorAlert({ message }: { message: string }) {
  return (
    <p className="rounded-xl border border-error-soft bg-canvas px-3 py-2 text-xs text-error-deep" role="alert">
      {message}
    </p>
  );
}

function LoadingState({ label }: { label: string }) {
  return <p className="text-xs text-mute">{label}</p>;
}

function NotFoundState() {
  return (
    <div className="rounded-xl border border-hairline bg-canvas px-4 py-12 text-center text-xs text-mute">
      MCP 服务不存在
    </div>
  );
}
