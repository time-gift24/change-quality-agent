import { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../../components/ui/table";
import type { McpServerTool } from "../types";

type McpDetailToolsPanelProps = {
  tools: McpServerTool[];
};

function ToolRow({ tool }: { tool: McpServerTool }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <TableRow>
        <TableCell className="w-[280px] px-4 font-mono text-xs text-ink">{tool.name}</TableCell>
        <TableCell className="px-4 text-xs text-body">{tool.description ?? "无描述"}</TableCell>
        <TableCell className="w-[110px] shrink-0 px-4 text-right">
          <button
            className="text-2xs text-mute transition-colors hover:text-ink"
            onClick={() => setExpanded((v) => !v)}
            type="button"
          >
            查看 schema {expanded ? "▴" : "▾"}
          </button>
        </TableCell>
      </TableRow>
      {expanded ? (
        <TableRow>
          <TableCell className="px-4 pb-3" colSpan={3}>
            <pre className="overflow-x-auto rounded-md border border-hairline bg-canvas-soft px-3 py-2 font-mono text-2xs text-body">
              {JSON.stringify(tool.input_schema, null, 2)}
            </pre>
          </TableCell>
        </TableRow>
      ) : null}
    </>
  );
}

export function McpDetailToolsPanel({ tools }: McpDetailToolsPanelProps) {
  if (tools.length === 0) {
    return (
      <div className="rounded-xl border border-hairline bg-canvas py-12 text-center text-xs text-mute">
        暂无工具快照。
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-hairline bg-canvas">
      <Table>
        <TableHeader>
          <TableRow className="bg-canvas-soft">
            <TableHead className="px-4">
              工具名
            </TableHead>
            <TableHead className="px-4">
              描述
            </TableHead>
            <TableHead className="w-[110px] shrink-0 px-4 text-right">
              Schema
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tools.map((tool) => (
            <ToolRow key={tool.name} tool={tool} />
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
