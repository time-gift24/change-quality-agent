import type { ComponentProps } from "react";
import { Link } from "react-router-dom";
import { Button } from "../../../components/ui/button";
import { Select } from "../../../components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../../components/ui/table";
import type { McpServerSummary } from "../types";
import { McpRowActionsMenu } from "./McpRowActionsMenu";
import { McpStatusBadge } from "./McpStatusBadge";
import { getMcpErrorMessage } from "./errorMessages";
import type { McpStatusFilter } from "../pages/McpListPage";

type McpServerTableProps = {
  servers: McpServerSummary[];
  searchText: string;
  statusFilter: McpStatusFilter;
  loading: boolean;
  error: Error | null;
  pending: boolean;
  onSearchTextChange: (next: string) => void;
  onStatusFilterChange: (next: McpStatusFilter) => void;
  onRefresh: () => void;
  onCreateServer: () => void;
  onStartServer: (serverId: string) => void;
  onStopServer: (serverId: string) => void;
  onRestartServer: (serverId: string) => void;
  onCheckServer: (serverId: string) => void;
  onDeleteServer: (serverId: string) => void;
};

function getCommandSummary(server: McpServerSummary) {
  if (server.transport === "http") return server.url ?? "-";
  return server.command ?? "-";
}

function getConfigSummary(server: McpServerSummary) {
  if (server.transport === "http") return server.url ?? "-";
  if (server.args.length > 0) return server.args.join(" ");
  return "未配置 args";
}

function formatLastChecked(value: string | null) {
  if (!value) return "未检查";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("zh-CN", {
    day: "2-digit",
    hour: "2-digit",
    hour12: false,
    minute: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

export function McpServerTable({
  servers,
  searchText,
  statusFilter,
  loading,
  error,
  pending: _pending,
  onSearchTextChange,
  onStatusFilterChange,
  onRefresh,
  onCreateServer,
  onStartServer,
  onStopServer,
  onRestartServer,
  onCheckServer,
  onDeleteServer,
}: McpServerTableProps) {
  const errorMessage = getMcpErrorMessage(error);

  return (
    <div className="rounded-3xl border border-hairline-soft bg-canvas p-3 shadow-sm shadow-primary/5">
      {/* Toolbar */}
      <div className="mb-3 flex flex-col gap-2 rounded-2xl bg-canvas-soft/70 px-2.5 py-2.5 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="relative">
            <svg
              aria-hidden="true"
              className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-mute"
              fill="none"
              stroke="currentColor"
              strokeLinecap="round"
              strokeWidth="2"
              viewBox="0 0 24 24"
            >
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.3-4.3" />
            </svg>
            <input
              aria-label="搜索 MCP 服务"
              className="h-9 w-full rounded-lg border border-hairline bg-canvas pl-9 pr-3 text-xs text-ink outline-none transition-colors placeholder:text-mute focus:border-primary focus:ring-2 focus:ring-primary/15 sm:w-64"
              onChange={(e) => onSearchTextChange(e.target.value)}
              placeholder="按名称搜索…"
              type="search"
              value={searchText}
            />
          </div>

          <Select
            aria-label="状态筛选"
            onChange={(e) => onStatusFilterChange(e.target.value as McpStatusFilter)}
            value={statusFilter}
          >
            <option value="all">全部状态</option>
            <option value="running">Running</option>
            <option value="stopped">Stopped</option>
            <option value="error">Error</option>
            <option value="starting">Starting</option>
            <option value="stopping">Stopping</option>
            <option value="unknown">Unknown</option>
          </Select>

          <Button onClick={onRefresh} variant="secondary">
            刷新
          </Button>
        </div>

        <Button
          aria-label="新增 MCP Server"
          className="w-full sm:w-auto"
          onClick={onCreateServer}
          variant="primary"
        >
          + 新增 Server
        </Button>
      </div>

      {/* Table */}
      <div className="overflow-x-auto pb-2">
        <Table className="min-w-[1040px] border-separate border-spacing-y-2">
          <TableHeader>
            <TableRow className="border-0">
              <TableHead className="w-[24%] px-4 font-sans text-2xs font-semibold tracking-[0.12em] text-stone">
                MCP 服务
              </TableHead>
              <TableHead className="w-[132px] font-sans text-2xs font-semibold tracking-[0.12em] text-stone">
                启用策略
              </TableHead>
              <TableHead className="w-[28%] font-sans text-2xs font-semibold tracking-[0.12em] text-stone">
                连接配置
              </TableHead>
              <TableHead className="w-[96px] text-center font-sans text-2xs font-semibold tracking-[0.12em] text-stone">
                工具
              </TableHead>
              <TableHead className="w-[136px] font-sans text-2xs font-semibold tracking-[0.12em] text-stone">
                运行状态
              </TableHead>
              <TableHead className="w-[156px] font-sans text-2xs font-semibold tracking-[0.12em] text-stone">
                最近检查
              </TableHead>
              <TableHead className="w-[72px] text-center font-sans text-2xs font-semibold tracking-[0.12em] text-stone">
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
            ) : errorMessage ? (
              <TableRow>
                <TableCell className="rounded-xl border border-error-soft bg-canvas px-3 py-2 text-xs text-error-deep" colSpan={7} role="alert">
                  {errorMessage}
                </TableCell>
              </TableRow>
            ) : servers.length === 0 ? (
              <TableRow>
                <TableCell className="rounded-xl bg-canvas-soft/60 py-12 text-center text-xs text-mute" colSpan={7}>
                  暂无 MCP 服务，点击
                  <Button
                    className="mx-1 h-auto px-1 py-0"
                    onClick={onCreateServer}
                    variant="ghost"
                  >
                    + 新增 Server
                  </Button>
                  开始添加。
                </TableCell>
              </TableRow>
            ) : (
              servers.map((server) => (
                <McpServerMetricRow
                  key={server.id}
                  onCheckServer={onCheckServer}
                  onDeleteServer={onDeleteServer}
                  onRestartServer={onRestartServer}
                  onStartServer={onStartServer}
                  onStopServer={onStopServer}
                  server={server}
                />
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between border-t border-hairline px-2 pt-2 text-2xs text-mute font-mono">
        <span>
          共 {servers.length} 个服务
          {statusFilter !== "all" ? ` · 显示 ${servers.length} 个` : ""}
        </span>
        <span>全部加载</span>
      </div>
    </div>
  );
}

type McpServerMetricRowProps = {
  server: McpServerSummary;
  onStartServer: (serverId: string) => void;
  onStopServer: (serverId: string) => void;
  onRestartServer: (serverId: string) => void;
  onCheckServer: (serverId: string) => void;
  onDeleteServer: (serverId: string) => void;
};

function McpServerMetricRow({
  server,
  onCheckServer,
  onDeleteServer,
  onRestartServer,
  onStartServer,
  onStopServer,
}: McpServerMetricRowProps) {
  const commandSummary = getCommandSummary(server);
  const configSummary = getConfigSummary(server);

  return (
    <TableRow className="group border-0">
      <MetricCell className="rounded-l-3xl border-l px-4 py-4">
        <Link
          className="block min-w-0 rounded-2xl focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
          to={`/mcp/${server.id}`}
        >
          <p className="truncate text-sm font-semibold tracking-tight text-ink transition-colors group-hover:text-primary-deep">
            {server.name}
          </p>
          <p className="mt-1 truncate text-2xs uppercase tracking-[0.14em] text-stone">
            {server.transport} server
          </p>
        </Link>
      </MetricCell>

      <MetricCell>
        <div className="flex flex-col items-start justify-center gap-1">
          <span
            className={`inline-flex h-6 items-center whitespace-nowrap rounded-full px-2.5 text-2xs font-semibold ${
              server.enabled
                ? "bg-primary-soft text-primary-deep"
                : "border border-hairline bg-canvas text-body"
            }`}
          >
            {server.enabled ? "已启用" : "已停用"}
          </span>
          <span className="whitespace-nowrap text-2xs text-mute">目标 {server.desired_state}</span>
        </div>
      </MetricCell>

      <MetricCell>
        <div className="flex min-w-0 flex-col gap-1.5">
          <div className="flex min-w-0 items-center gap-2">
            <span className="inline-flex h-6 shrink-0 items-center rounded-full border border-hairline bg-canvas px-2.5 font-mono text-2xs text-ink">
              {server.transport}
            </span>
            <span className="truncate text-2xs text-mute">
              {server.transport === "http" ? "URL" : "command"}:
              {" "}
              <span className="font-mono text-body">{commandSummary}</span>
            </span>
          </div>
          <span className="block truncate rounded-full bg-canvas px-3 py-1.5 font-mono text-xs text-ink">
            {configSummary}
          </span>
        </div>
      </MetricCell>

      <MetricCell>
        <div
          aria-label={`${server.name} 工具数 ${server.tool_count}`}
          className="flex items-baseline justify-center gap-1"
        >
          <span className="font-mono text-sm font-semibold leading-none tracking-tight text-ink">
            {server.tool_count}
          </span>
          <span className="text-2xs text-mute">
            {server.tool_count === 1 ? "tool" : "tools"}
          </span>
        </div>
      </MetricCell>

      <MetricCell>
        <div className="flex flex-col items-start justify-center gap-1.5">
          <McpStatusBadge status={server.runtime_status} />
          {server.last_error ? (
            <span className="inline-flex max-w-full rounded-full bg-error-soft px-2 py-0.5 text-2xs text-error-deep">
              最近错误
            </span>
          ) : null}
        </div>
      </MetricCell>

      <MetricCell>
        <span className="font-mono text-2xs text-body">
          {formatLastChecked(server.last_checked_at)}
        </span>
      </MetricCell>

      <MetricCell className="rounded-r-3xl border-r text-center">
        <McpRowActionsMenu
          onCheck={onCheckServer}
          onDelete={onDeleteServer}
          onRestart={onRestartServer}
          onStart={onStartServer}
          onStop={onStopServer}
          runtimeStatus={server.runtime_status}
          serverId={server.id}
          serverName={server.name}
        />
      </MetricCell>
    </TableRow>
  );
}

type MetricCellProps = ComponentProps<typeof TableCell>;

function MetricCell({ className, ...props }: MetricCellProps) {
  return (
    <TableCell
      className={`border-y border-hairline-soft bg-canvas-soft/55 align-middle transition-colors group-hover:border-primary/20 group-hover:bg-primary-soft/30 ${className ?? ""}`}
      {...props}
    />
  );
}
