import type { McpServerDetail } from "../types";
import { getMcpErrorMessage } from "./errorMessages";

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
  const errorMessage = getMcpErrorMessage(error);
  const configTabId = server ? `mcp-config-tab-${server.id}` : "mcp-config-tab";
  const toolsTabId = server ? `mcp-tools-tab-${server.id}` : "mcp-tools-tab";
  const configPanelId = server ? `mcp-config-panel-${server.id}` : "mcp-config-panel";
  const toolsPanelId = server ? `mcp-tools-panel-${server.id}` : "mcp-tools-panel";

  return (
    <section
      aria-label="MCP 服务详情"
      className="flex h-full min-h-0 flex-col rounded-2xl border border-hairline bg-canvas/90"
      role="region"
    >
      {!server ? (
        loading || errorMessage ? (
          <div className="flex flex-1 flex-col justify-center gap-2 p-6">
            {loading ? <p className="text-sm text-mute">加载详情中...</p> : null}
            {errorMessage ? (
              <p className="rounded-lg bg-error-soft px-3 py-2 text-xs text-error-deep" role="alert">
                {errorMessage}
              </p>
            ) : null}
          </div>
        ) : (
          <div className="flex flex-1 items-center justify-center p-6 text-sm text-mute">
            请选择一个 MCP 服务。
          </div>
        )
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
                aria-controls={configPanelId}
                aria-selected={activeTab === "configuration"}
                className={`rounded-t-lg px-3 py-1.5 text-sm ${
                  activeTab === "configuration"
                    ? "bg-primary-soft text-primary-deep"
                    : "text-body hover:text-ink"
                }`}
                id={configTabId}
                onClick={() => onTabChange("configuration")}
                role="tab"
                type="button"
              >
                配置
              </button>
              <button
                aria-controls={toolsPanelId}
                aria-selected={activeTab === "tools"}
                className={`rounded-t-lg px-3 py-1.5 text-sm ${
                  activeTab === "tools"
                    ? "bg-primary-soft text-primary-deep"
                    : "text-body hover:text-ink"
                }`}
                id={toolsTabId}
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
            {errorMessage ? (
              <p className="rounded-lg bg-error-soft px-3 py-2 text-xs text-error-deep" role="alert">
                {errorMessage}
              </p>
            ) : null}

            {!loading && !errorMessage && activeTab === "configuration" ? (
              <div
                aria-labelledby={configTabId}
                id={configPanelId}
                role="tabpanel"
              >
                <dl className="grid grid-cols-1 gap-3 text-sm text-body md:grid-cols-2">
                  <InfoItem label="ID" value={server.id} />
                  <InfoItem label="Transport" value={server.transport} />
                  <InfoItem label="Command" value={server.command ?? "-"} />
                  <InfoItem label="URL" value={server.url ?? "-"} />
                  <InfoItem label="Enabled" value={server.enabled ? "true" : "false"} />
                  <InfoItem label="Args" value={server.args.length > 0 ? server.args.join(" ") : "-"} />
                </dl>
              </div>
            ) : null}

            {!loading && !errorMessage && activeTab === "tools" ? (
              <div
                aria-labelledby={toolsTabId}
                id={toolsPanelId}
                role="tabpanel"
              >
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
                        <pre className="mt-2 overflow-x-auto rounded-md border border-hairline bg-canvas px-2 py-1 text-2xs text-body">
                          <code>{JSON.stringify(tool.input_schema, null, 2)}</code>
                        </pre>
                      </li>
                    ))
                  )}
                </ul>
              </div>
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
