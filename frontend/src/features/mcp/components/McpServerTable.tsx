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
    <div className="rounded-xl border border-hairline bg-canvas">
      {/* Toolbar */}
      <div className="flex items-center gap-2 border-b border-hairline px-3 py-2">
        <div className="relative flex-1">
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
            className="h-9 w-64 rounded-lg border border-hairline bg-canvas pl-9 pr-3 text-xs text-ink outline-none transition-colors placeholder:text-mute focus:border-primary focus:ring-2 focus:ring-primary/15"
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

        <div className="flex-1" />

        <Button onClick={onRefresh} variant="secondary">
          刷新
        </Button>

        <Button
          aria-label="新增 MCP Server"
          onClick={onCreateServer}
          variant="primary"
        >
          + 新增 Server
        </Button>
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow className="bg-canvas-soft">
            <TableHead>
              名称
            </TableHead>
            <TableHead className="hidden w-[120px] sm:table-cell">
              状态
            </TableHead>
            <TableHead className="hidden w-[80px] text-right sm:table-cell">
              工具
            </TableHead>
            <TableHead className="hidden w-[160px] sm:table-cell">
              最近检查
            </TableHead>
            <TableHead className="w-[56px] px-2 text-center">
              <span className="sr-only">操作</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {loading ? (
            <TableRow>
              <TableCell className="py-8 text-center text-xs text-mute" colSpan={5}>
                加载中…
              </TableCell>
            </TableRow>
          ) : errorMessage ? (
            <TableRow>
              <TableCell className="border border-error-soft bg-canvas px-3 py-2 text-xs text-error-deep" colSpan={5} role="alert">
                {errorMessage}
              </TableCell>
            </TableRow>
          ) : servers.length === 0 ? (
            <TableRow>
              <TableCell className="py-12 text-center text-xs text-mute" colSpan={5}>
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
              <TableRow
                key={server.id}
                className="transition-colors hover:bg-canvas-soft"
              >
                <TableCell>
                  <Link
                    className="block rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
                    to={`/mcp/${server.id}`}
                  >
                    <p className="text-sm font-medium text-ink">{server.name}</p>
                      <p className="text-2xs text-mute font-mono">{server.transport}</p>
                    </Link>
                </TableCell>
                <TableCell className="hidden sm:table-cell">
                  <McpStatusBadge status={server.runtime_status} />
                </TableCell>
                <TableCell className="hidden text-right sm:table-cell">
                  <span className="text-2xs tabular-nums font-mono text-body">
                    {server.tool_count}
                  </span>
                </TableCell>
                <TableCell className="hidden sm:table-cell">
                  <span className="text-2xs text-mute">
                    {server.last_checked_at ?? "-"}
                  </span>
                </TableCell>
                <TableCell className="px-2 text-center">
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
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      {/* Footer */}
      <div className="flex items-center justify-between border-t border-hairline px-3 py-2 text-2xs text-mute font-mono">
        <span>
          共 {servers.length} 个服务
          {statusFilter !== "all" ? ` · 显示 ${servers.length} 个` : ""}
        </span>
        <span>全部加载</span>
      </div>
    </div>
  );
}
