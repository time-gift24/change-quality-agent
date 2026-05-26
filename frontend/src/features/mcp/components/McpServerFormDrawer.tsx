import { useEffect, useState, type FormEvent } from "react";

import type {
  McpDesiredState,
  McpServerCreate,
  McpServerDetail,
  McpServerUpdate,
  McpTransport,
} from "../types";

type McpServerFormDrawerProps = {
  open: boolean;
  mode: "create" | "edit";
  server: McpServerDetail | null;
  pending: boolean;
  onClose: () => void;
  onCreate: (payload: McpServerCreate) => Promise<void>;
  onUpdate: (serverId: string, payload: McpServerUpdate) => Promise<void>;
};

const DEFAULT_TRANSPORT: McpTransport = "stdio";
const DEFAULT_DESIRED_STATE: McpDesiredState = "running";

export function McpServerFormDrawer({
  open,
  mode,
  server,
  pending,
  onClose,
  onCreate,
  onUpdate,
}: McpServerFormDrawerProps) {
  const [name, setName] = useState("");
  const [transport, setTransport] = useState<McpTransport>(DEFAULT_TRANSPORT);
  const [command, setCommand] = useState("");
  const [url, setUrl] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [desiredState, setDesiredState] = useState<McpDesiredState>(
    DEFAULT_DESIRED_STATE,
  );

  useEffect(() => {
    if (!open) {
      return;
    }

    if (mode === "edit" && server) {
      setName(server.name);
      setTransport(server.transport);
      setCommand(server.command ?? "");
      setUrl(server.url ?? "");
      setEnabled(server.enabled);
      setDesiredState(server.desired_state);
      return;
    }

    setName("");
    setTransport(DEFAULT_TRANSPORT);
    setCommand("");
    setUrl("");
    setEnabled(true);
    setDesiredState(DEFAULT_DESIRED_STATE);
  }, [mode, open, server]);

  if (!open) {
    return null;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const nextName = name.trim();
    if (!nextName) {
      return;
    }

    if (mode === "create") {
      const payload: McpServerCreate = {
        desired_state: desiredState,
        enabled,
        name: nextName,
        transport,
      };

      if (transport === "stdio") {
        payload.command = command.trim() || null;
      }

      if (transport === "http") {
        payload.url = url.trim() || null;
      }

      await onCreate(payload);
      return;
    }

    if (!server) {
      return;
    }

    const payload: McpServerUpdate = {
      desired_state: desiredState,
      enabled,
      name: nextName,
    };

    if (transport === "stdio") {
      payload.command = command.trim() || null;
      payload.url = null;
    }

    if (transport === "http") {
      payload.url = url.trim() || null;
      payload.command = null;
    }

    await onUpdate(server.id, payload);
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-ink/25">
      <div className="h-full w-full max-w-md border-l border-hairline bg-canvas shadow-xl">
        <div className="flex items-center justify-between border-b border-hairline px-4 py-3">
          <h2 className="text-base font-semibold text-ink">
            {mode === "create" ? "新增 MCP 服务" : "编辑 MCP 服务"}
          </h2>
          <button
            className="rounded-md px-2 py-1 text-sm text-body transition hover:bg-canvas-soft"
            onClick={onClose}
            type="button"
          >
            关闭
          </button>
        </div>

        <form className="space-y-4 p-4" onSubmit={(event) => void handleSubmit(event)}>
          <div>
            <label className="block text-xs text-body" htmlFor="mcp-form-name">
              服务名称
            </label>
            <input
              className="mt-1 w-full rounded-lg border border-hairline px-3 py-2 text-sm"
              id="mcp-form-name"
              onChange={(event) => setName(event.target.value)}
              required
              value={name}
            />
          </div>

          <div>
            <label className="block text-xs text-body" htmlFor="mcp-form-transport">
              传输方式
            </label>
            <select
              className="mt-1 w-full rounded-lg border border-hairline px-3 py-2 text-sm"
              disabled={mode === "edit"}
              id="mcp-form-transport"
              onChange={(event) => setTransport(event.target.value as McpTransport)}
              value={transport}
            >
              <option value="stdio">stdio</option>
              <option value="http">http</option>
            </select>
          </div>

          {transport === "stdio" ? (
            <div>
              <label className="block text-xs text-body" htmlFor="mcp-form-command">
                command
              </label>
              <input
                className="mt-1 w-full rounded-lg border border-hairline px-3 py-2 text-sm"
                id="mcp-form-command"
                onChange={(event) => setCommand(event.target.value)}
                value={command}
              />
            </div>
          ) : (
            <div>
              <label className="block text-xs text-body" htmlFor="mcp-form-url">
                url
              </label>
              <input
                className="mt-1 w-full rounded-lg border border-hairline px-3 py-2 text-sm"
                id="mcp-form-url"
                onChange={(event) => setUrl(event.target.value)}
                type="url"
                value={url}
              />
            </div>
          )}

          <div>
            <label className="block text-xs text-body" htmlFor="mcp-form-desired">
              desired_state
            </label>
            <select
              className="mt-1 w-full rounded-lg border border-hairline px-3 py-2 text-sm"
              id="mcp-form-desired"
              onChange={(event) => setDesiredState(event.target.value as McpDesiredState)}
              value={desiredState}
            >
              <option value="running">running</option>
              <option value="stopped">stopped</option>
            </select>
          </div>

          <label className="flex items-center gap-2 text-sm text-body" htmlFor="mcp-form-enabled">
            <input
              checked={enabled}
              id="mcp-form-enabled"
              onChange={(event) => setEnabled(event.target.checked)}
              type="checkbox"
            />
            enabled
          </label>

          <div className="flex justify-end gap-2 border-t border-hairline pt-3">
            <button
              className="rounded-lg border border-hairline px-3 py-1.5 text-sm text-body"
              onClick={onClose}
              type="button"
            >
              取消
            </button>
            <button
              className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-on-primary disabled:cursor-not-allowed disabled:opacity-50"
              disabled={pending}
              type="submit"
            >
              {pending ? "提交中..." : "保存"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
