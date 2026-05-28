import { Link } from "react-router-dom";
import type { ReactNode } from "react";

import { Button } from "../../../components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../../components/ui/table";
import type { LlmProviderSummary } from "../types";

type LlmProviderTableProps = {
  providers: LlmProviderSummary[];
  loading: boolean;
  error: Error | null;
  searchText: string;
  onSearchTextChange: (next: string) => void;
  onRefresh: () => void;
  onCreateProvider: () => void;
};

export function LlmProviderTable({
  providers,
  loading,
  error,
  searchText,
  onSearchTextChange,
  onRefresh,
  onCreateProvider,
}: LlmProviderTableProps) {
  return (
    <div className="rounded-3xl border border-hairline-soft bg-canvas p-3 shadow-sm shadow-primary/5">
      <div className="mb-3 flex flex-col gap-2 rounded-2xl bg-canvas-soft/70 px-2.5 py-2.5 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <input
            aria-label="搜索 LLM Provider"
            autoComplete="off"
            className="h-10 w-full rounded-lg border border-hairline bg-canvas px-3 text-sm text-ink outline-none transition-colors placeholder:text-mute focus:border-primary focus:ring-2 focus:ring-primary/15 sm:w-64"
            name="llm_provider_search"
            onChange={(event) => onSearchTextChange(event.target.value)}
            placeholder="按名称或类型搜索…"
            type="search"
            value={searchText}
          />
          <Button aria-busy={loading} disabled={loading} onClick={onRefresh} variant="secondary">
            {loading ? "刷新中…" : "刷新"}
          </Button>
        </div>
        <Button
          aria-label="新增 Provider"
          className="w-full sm:w-auto"
          onClick={onCreateProvider}
          variant="primary"
        >
          + 新增 Provider
        </Button>
      </div>

      <p className="mb-2 text-xs text-mute md:hidden">表格可横向滑动查看更多字段。</p>
      <div className="overflow-x-auto pb-2">
        <Table className="min-w-[940px] border-separate border-spacing-y-2">
          <TableHeader>
            <TableRow className="border-0">
              <TableHead className="w-[26%] px-4 font-sans text-2xs font-semibold tracking-[0.12em] text-stone">
                Provider
              </TableHead>
              <TableHead className="w-[130px] font-sans text-2xs font-semibold tracking-[0.12em] text-stone">
                类型
              </TableHead>
              <TableHead className="w-[28%] font-sans text-2xs font-semibold tracking-[0.12em] text-stone">
                Base URL
              </TableHead>
              <TableHead className="w-[120px] font-sans text-2xs font-semibold tracking-[0.12em] text-stone">
                API Key
              </TableHead>
              <TableHead className="w-[120px] font-sans text-2xs font-semibold tracking-[0.12em] text-stone">
                状态
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell className="rounded-xl bg-canvas-soft/60 py-8 text-center text-xs text-mute" colSpan={5}>
                  加载中…
                </TableCell>
              </TableRow>
            ) : error ? (
              <TableRow>
                <TableCell className="rounded-xl border border-error-soft bg-canvas px-3 py-2 text-xs text-error-deep" colSpan={5} role="alert">
                  {error.message}
                </TableCell>
              </TableRow>
            ) : providers.length === 0 ? (
              <TableRow>
                <TableCell className="rounded-xl bg-canvas-soft/60 py-12 text-center text-xs text-mute" colSpan={5}>
                  暂无 LLM Provider。
                </TableCell>
              </TableRow>
            ) : (
              providers.map((provider) => (
                <TableRow className="group border-0" key={provider.id}>
                  <MetricCell className="rounded-l-3xl border-l px-4 py-4">
                    <Link
                      className="block min-w-0 rounded-2xl focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
                      to={`/llm-providers/${provider.id}`}
                    >
                      <p className="truncate text-sm font-semibold tracking-tight text-ink transition-colors group-hover:text-primary-deep">
                        {provider.display_name}
                      </p>
                      <p className="mt-1 truncate font-mono text-xs text-stone">
                        {provider.id}
                      </p>
                    </Link>
                  </MetricCell>
                  <MetricCell>
                    <span className="inline-flex h-7 items-center rounded-full border border-hairline bg-canvas px-2.5 font-mono text-xs text-ink">
                      {provider.provider_type}
                    </span>
                  </MetricCell>
                  <MetricCell>
                    <span className="block truncate rounded-full bg-canvas px-3 py-1.5 font-mono text-xs text-ink">
                      {provider.base_url ?? "默认 LangChain provider endpoint"}
                    </span>
                  </MetricCell>
                  <MetricCell>
                    <span className={provider.api_key_configured ? "text-success" : "text-mute"}>
                      {provider.api_key_configured ? "已配置" : "未配置"}
                    </span>
                  </MetricCell>
                  <MetricCell className="rounded-r-3xl border-r">
                    <span className={provider.enabled ? "text-primary-deep" : "text-mute"}>
                      {provider.enabled ? "已启用" : "已停用"}
                    </span>
                  </MetricCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
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
