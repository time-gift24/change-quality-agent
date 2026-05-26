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
            navigate(`/mcp/${created.id}`);
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
              navigate(`/mcp/${targetServerId}`);
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
    <div className="grid max-w-6xl gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
      <div className="min-w-0 space-y-3">{children}</div>
      <aside className="space-y-3">{aside}</aside>
    </div>
  );
}

function FormSideNote({ title, lines }: { title: string; lines: string[] }) {
  return (
    <div className="rounded-xl border border-hairline bg-canvas px-4 py-3">
      <h2 className="text-xs font-semibold text-ink">{title}</h2>
      <ul className="mt-2 space-y-2 text-2xs leading-relaxed text-mute">
        {lines.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </div>
  );
}

function ServerSideNote({ server }: { server: McpServerDetail }) {
  return (
    <div className="rounded-xl border border-hairline bg-canvas px-4 py-3">
      <h2 className="text-xs font-semibold text-ink">当前状态</h2>
      <dl className="mt-3 space-y-2 text-2xs">
        <SideRow label="运行状态" value={<McpStatusBadge status={server.runtime_status} />} />
        <SideRow label="工具数量" value={server.tool_count} />
        <SideRow label="最近检查" value={server.last_checked_at ?? "-"} />
      </dl>
    </div>
  );
}

function SideRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-mute">{label}</dt>
      <dd className="text-right font-mono text-ink">{value}</dd>
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
