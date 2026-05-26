import type { McpServerDetail } from "../types";

export type McpDetailTab = "configuration" | "tools";

type McpServerDetailProps = {
  server: McpServerDetail | null;
  loading: boolean;
  error: Error | null;
  activeTab: McpDetailTab;
  pending: boolean;
  onTabChange: (next: McpDetailTab) => void;
  onEditServer: () => void;
  onDeleteServer: () => void;
};

export function McpServerDetail({
  server,
  loading,
  error,
  activeTab,
  pending,
  onTabChange,
  onEditServer,
  onDeleteServer,
}: McpServerDetailProps) {
  return (
    <section
      aria-label="MCP 服务详情"
      className="flex h-full min-h-0 flex-col rounded-2xl border border-hairline bg-canvas/90"
      role="region"
    >
      {!server ? (
        <div className="flex flex-1 items-center justify-center p-6 text-sm text-mute">
          请选择一个 MCP 服务。
        </div>
      ) : (
        <>
          <header className="space-y-3 border-b border-hairline p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-ink">{server.name}</h2>
                <p className="mt-1 text-xs text-body">
                  {server.transport} · desired {server.desired_state}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  className="rounded-lg border border-hairline px-3 py-1.5 text-xs text-body transition hover:border-primary hover:text-primary"
                  onClick={onEditServer}
                  type="button"
                >
                  编辑
                </button>
                <button
                  className="rounded-lg border border-error px-3 py-1.5 text-xs text-error-deep transition hover:bg-error-soft disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={pending}
                  onClick={onDeleteServer}
                  type="button"
                >
                  删除
                </button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 rounded-xl border border-hairline bg-canvas-soft p-3 text-xs text-body md:grid-cols-4">
              <StatItem label="runtime" value={server.runtime_status} />
              <StatItem label="desired" value={server.desired_state} />
              <StatItem label="tools" value={String(server.tool_count)} />
              <StatItem label="last check" value={server.last_checked_at ?? "-"} />
            </div>
            {server.last_error ? (
              <p className="rounded-lg bg-error-soft px-3 py-2 text-xs text-error-deep" role="alert">
                {server.last_error}
              </p>
            ) : null}
          </header>

          <div className="border-b border-hairline px-4 pt-3">
            <div aria-label="详情标签" className="flex gap-2" role="tablist">
              <button
                aria-selected={activeTab === "configuration"}
                className={`rounded-t-lg px-3 py-1.5 text-sm ${
                  activeTab === "configuration"
                    ? "bg-primary-soft text-primary-deep"
                    : "text-body hover:text-ink"
                }`}
                onClick={() => onTabChange("configuration")}
                role="tab"
                type="button"
              >
                配置
              </button>
              <button
                aria-selected={activeTab === "tools"}
                className={`rounded-t-lg px-3 py-1.5 text-sm ${
                  activeTab === "tools"
                    ? "bg-primary-soft text-primary-deep"
                    : "text-body hover:text-ink"
                }`}
                onClick={() => onTabChange("tools")}
                role="tab"
                type="button"
              >
                工具快照
              </button>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            {loading ? <p className="text-sm text-mute">加载详情中...</p> : null}
            {error ? (
              <p className="rounded-lg bg-error-soft px-3 py-2 text-xs text-error-deep" role="alert">
                {error.message}
              </p>
            ) : null}

            {!loading && !error && activeTab === "configuration" ? (
              <dl className="grid grid-cols-1 gap-3 text-sm text-body md:grid-cols-2">
                <InfoItem label="ID" value={server.id} />
                <InfoItem label="Transport" value={server.transport} />
                <InfoItem label="Command" value={server.command ?? "-"} />
                <InfoItem label="URL" value={server.url ?? "-"} />
                <InfoItem label="Enabled" value={server.enabled ? "true" : "false"} />
                <InfoItem label="Args" value={server.args.length > 0 ? server.args.join(" ") : "-"} />
              </dl>
            ) : null}

            {!loading && !error && activeTab === "tools" ? (
              <ul aria-label="工具快照列表" className="space-y-2" role="list">
                {server.tools.length === 0 ? (
                  <li className="rounded-lg border border-hairline bg-canvas-soft px-3 py-2 text-xs text-mute">
                    暂无工具快照。
                  </li>
                ) : (
                  server.tools.map((tool) => (
                    <li
                      className="rounded-lg border border-hairline bg-canvas-soft px-3 py-2"
                      key={tool.name}
                    >
                      <p className="text-sm font-medium text-ink">{tool.name}</p>
                      <p className="mt-1 text-xs text-body">{tool.description ?? "无描述"}</p>
                    </li>
                  ))
                )}
              </ul>
            ) : null}
          </div>
        </>
      )}
    </section>
  );
}

function StatItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-2xs uppercase text-mute">{label}</p>
      <p className="mt-1 truncate font-medium text-ink">{value}</p>
    </div>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-hairline bg-canvas p-3">
      <dt className="text-2xs uppercase text-mute">{label}</dt>
      <dd className="mt-1 break-all text-sm text-ink">{value}</dd>
    </div>
  );
}
