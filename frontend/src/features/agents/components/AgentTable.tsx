import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { Button } from "../../../components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../../components/ui/table";
import type { LlmProviderSummary } from "../../llmProviders/types";
import type { AgentSummary } from "../types";

type AgentTableProps = {
  agents: AgentSummary[];
  providers: LlmProviderSummary[];
  loading: boolean;
  error: Error | null;
  searchText: string;
  onSearchTextChange: (next: string) => void;
  onRefresh: () => void;
  onCreateAgent: () => void;
};

export function AgentTable({
  agents,
  providers,
  loading,
  error,
  searchText,
  onSearchTextChange,
  onRefresh,
  onCreateAgent,
}: AgentTableProps) {
  return (
    <div className="rounded-3xl border border-hairline-soft bg-canvas p-3 shadow-sm shadow-primary/5">
      <div className="mb-3 flex flex-col gap-2 rounded-2xl bg-canvas-soft/70 px-2.5 py-2.5 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <input
            aria-label="搜索 Agent"
            autoComplete="off"
            className="h-10 w-full rounded-lg border border-hairline bg-canvas px-3 text-sm text-ink outline-none transition-colors placeholder:text-mute focus:border-primary focus:ring-2 focus:ring-primary/15 sm:w-72"
            name="agent_search"
            onChange={(event) => onSearchTextChange(event.target.value)}
            placeholder="按名称、描述或模型搜索…"
            type="search"
            value={searchText}
          />
          <Button aria-busy={loading} disabled={loading} onClick={onRefresh} variant="secondary">
            {loading ? "刷新中…" : "刷新"}
          </Button>
        </div>
        <Button
          aria-label="新增 Agent"
          className="w-full sm:w-auto"
          onClick={onCreateAgent}
          variant="primary"
        >
          + 新增 Agent
        </Button>
      </div>

      <p className="mb-2 text-xs text-mute md:hidden">表格可横向滑动查看更多字段。</p>
      <div className="overflow-x-auto pb-2">
        <Table className="min-w-[1080px] border-separate border-spacing-y-2">
          <TableHeader>
            <TableRow className="border-0">
              <TableHead className="w-[24%] px-4 font-sans text-2xs font-semibold tracking-[0.12em] text-stone">
                Agent
              </TableHead>
              <TableHead className="w-[100px] font-sans text-2xs font-semibold tracking-[0.12em] text-stone">
                状态
              </TableHead>
              <TableHead className="w-[17%] font-sans text-2xs font-semibold tracking-[0.12em] text-stone">
                模型
              </TableHead>
              <TableHead className="w-[15%] font-sans text-2xs font-semibold tracking-[0.12em] text-stone">
                Provider
              </TableHead>
              <TableHead className="w-[16%] font-sans text-2xs font-semibold tracking-[0.12em] text-stone">
                Draft
              </TableHead>
              <TableHead className="w-[140px] font-sans text-2xs font-semibold tracking-[0.12em] text-stone">
                更新时间
              </TableHead>
              <TableHead className="w-[90px] font-sans text-2xs font-semibold tracking-[0.12em] text-stone">
                操作
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell className="rounded-xl bg-canvas-soft/60 py-8 text-center text-xs text-mute" colSpan={7}>
                  加载中…
                </TableCell>
              </TableRow>
            ) : error ? (
              <TableRow>
                <TableCell className="rounded-xl border border-error-soft bg-canvas px-3 py-2 text-xs text-error-deep" colSpan={7} role="alert">
                  {error.message}
                </TableCell>
              </TableRow>
            ) : agents.length === 0 ? (
              <TableRow>
                <TableCell className="rounded-xl bg-canvas-soft/60 py-12 text-center text-xs text-mute" colSpan={7}>
                  暂无 Agent。
                </TableCell>
              </TableRow>
            ) : (
              agents.map((agent) => (
                <AgentRow agent={agent} key={agent.id} providers={providers} />
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function AgentRow({
  agent,
  providers,
}: {
  agent: AgentSummary;
  providers: LlmProviderSummary[];
}) {
  const modelLabel = agent.latest_version?.model ?? "未发布";
  const provider = agent.latest_version
    ? resolveProviderDisplay(agent.latest_version.provider_id, providers)
    : { disabled: false, label: "未发布" };
  const draftLabel = agent.has_draft ? "有 Draft" : "无 Draft";

  return (
    <TableRow className="group border-0">
      <MetricCell className="rounded-l-3xl border-l px-4 py-4">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold tracking-tight text-ink transition-colors group-hover:text-primary-deep">
            {agent.display_name}
          </p>
          <p className="mt-1 truncate font-mono text-xs text-stone">
            {agent.id}
          </p>
          {agent.description ? (
            <p className="mt-1 truncate text-xs text-mute">
              {agent.description}
            </p>
          ) : null}
        </div>
      </MetricCell>
      <MetricCell>
        <span className={agent.enabled ? "text-primary-deep" : "text-mute"}>
          {agent.enabled ? "已启用" : "已停用"}
        </span>
      </MetricCell>
      <MetricCell>
        <span className="block truncate rounded-full bg-canvas px-3 py-1.5 font-mono text-xs text-ink">
          {modelLabel}
        </span>
      </MetricCell>
      <MetricCell>
        <span className="block truncate text-xs text-body">{provider.label}</span>
        {provider.disabled ? (
          <span className="mt-1 block text-2xs text-mute">Provider 已停用</span>
        ) : null}
      </MetricCell>
      <MetricCell>
        <span className={agent.has_draft ? "text-ink" : "text-mute"}>
          {draftLabel}
        </span>
      </MetricCell>
      <MetricCell>
        <span className="font-mono text-xs text-body">
          {formatAgentUpdatedAt(agent.updated_at)}
        </span>
      </MetricCell>
      <MetricCell className="rounded-r-3xl border-r">
        <Link
          aria-label={`编辑 ${agent.display_name}`}
          className="inline-flex h-8 items-center justify-center rounded-lg border border-hairline bg-canvas px-3 text-xs font-medium text-body transition-colors hover:border-primary/40 hover:text-primary-deep focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
          to={`/agents/${agent.id}/edit`}
        >
          编辑
        </Link>
      </MetricCell>
    </TableRow>
  );
}

function MetricCell({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <TableCell className={`border-y border-hairline-soft bg-canvas-soft/70 py-3 text-xs text-body ${className}`}>
      {children}
    </TableCell>
  );
}

function resolveProviderDisplay(
  providerId: string | null,
  providers: LlmProviderSummary[],
): { disabled: boolean; label: string } {
  if (!providerId) return { disabled: false, label: "CodeAgent" };
  const provider = providers.find((item) => item.id === providerId);
  if (!provider) return { disabled: false, label: providerId };
  return { disabled: !provider.enabled, label: provider.display_name };
}

export function formatAgentUpdatedAt(value: string): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}
