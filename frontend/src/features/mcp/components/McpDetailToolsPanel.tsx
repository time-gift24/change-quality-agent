import { useState } from "react";
import type { McpServerTool } from "../types";

type McpDetailToolsPanelProps = {
  tools: McpServerTool[];
};

function ToolRow({ tool }: { tool: McpServerTool }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <tr className="border-b border-hairline last:border-0">
        <td className="w-[240px] px-3 py-2 font-mono text-xs text-ink">{tool.name}</td>
        <td className="px-3 py-2 text-xs text-body">{tool.description ?? "无描述"}</td>
        <td className="w-[120px] px-3 py-2">
          <button
            className="text-2xs text-mute transition-colors hover:text-ink"
            onClick={() => setExpanded((v) => !v)}
            type="button"
          >
            查看 schema {expanded ? "▴" : "▾"}
          </button>
        </td>
      </tr>
      {expanded ? (
        <tr>
          <td className="px-3 pb-2" colSpan={3}>
            <pre className="overflow-x-auto rounded-md border border-hairline bg-canvas-soft px-3 py-2 font-mono text-2xs text-body">
              {JSON.stringify(tool.input_schema, null, 2)}
            </pre>
          </td>
        </tr>
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
      <table className="w-full">
        <thead>
          <tr className="border-b border-hairline bg-canvas-soft">
            <th className="h-10 w-[240px] px-3 text-left text-2xs font-medium uppercase tracking-wide text-mute font-mono">
              工具名
            </th>
            <th className="h-10 px-3 text-left text-2xs font-medium uppercase tracking-wide text-mute font-mono">
              描述
            </th>
            <th className="h-10 w-[120px] px-3 text-left text-2xs font-medium uppercase tracking-wide text-mute font-mono">
              Schema
            </th>
          </tr>
        </thead>
        <tbody>
          {tools.map((tool) => (
            <ToolRow key={tool.name} tool={tool} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
