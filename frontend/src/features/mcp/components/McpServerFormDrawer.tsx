import {
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
} from "react";

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
const DEFAULT_DESIRED_STATE: McpDesiredState = "stopped";
const DEFAULT_ENABLED = false;
const REDACTED_VALUE = "********";
const FOCUSABLE_SELECTOR =
  "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex='-1'])";

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
  const [argsText, setArgsText] = useState("");
  const [envText, setEnvText] = useState("");
  const [headersText, setHeadersText] = useState("");
  const [enabled, setEnabled] = useState(DEFAULT_ENABLED);
  const [desiredState, setDesiredState] = useState<McpDesiredState>(
    DEFAULT_DESIRED_STATE,
  );
  const [validationMessage, setValidationMessage] = useState<string | null>(null);
  const drawerRef = useRef<HTMLDivElement | null>(null);
  const nameInputRef = useRef<HTMLInputElement | null>(null);
  const commandInputRef = useRef<HTMLInputElement | null>(null);
  const urlInputRef = useRef<HTMLInputElement | null>(null);
  const titleId = useId();
  const validationId = useId();

  useEffect(() => {
    if (!open) {
      return;
    }

    if (mode === "edit" && server) {
      setName(server.name);
      setTransport(server.transport);
      setCommand(server.command ?? "");
      setUrl(server.url ?? "");
      setArgsText(argsToText(server.args));
      setEnvText(keyValueMapToText(server.env));
      setHeadersText(keyValueMapToText(server.headers));
      setEnabled(server.enabled);
      setDesiredState(server.desired_state);
      setValidationMessage(null);
      return;
    }

    setName("");
    setTransport(DEFAULT_TRANSPORT);
    setCommand("");
    setUrl("");
    setArgsText("");
    setEnvText("");
    setHeadersText("");
    setEnabled(DEFAULT_ENABLED);
    setDesiredState(DEFAULT_DESIRED_STATE);
    setValidationMessage(null);
  }, [mode, open, server]);

  useEffect(() => {
    if (!open) {
      return;
    }

    nameInputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }

      if (event.key !== "Tab") {
        return;
      }

      const drawerElement = drawerRef.current;
      if (!drawerElement) {
        return;
      }

      const focusableElements = Array.from(
        drawerElement.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      );

      if (focusableElements.length === 0) {
        return;
      }

      const first = focusableElements[0];
      const last = focusableElements[focusableElements.length - 1];
      const active = document.activeElement as HTMLElement | null;

      if (!active || !drawerElement.contains(active)) {
        event.preventDefault();
        (event.shiftKey ? last : first)?.focus();
        return;
      }

      if (event.shiftKey && active === first) {
        event.preventDefault();
        last?.focus();
        return;
      }

      if (!event.shiftKey && active === last) {
        event.preventDefault();
        first?.focus();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose, open]);

  if (!open) {
    return null;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const nextName = name.trim();
    if (!nextName) {
      setValidationMessage("请填写服务名称。");
      nameInputRef.current?.focus();
      return;
    }

    if (transport === "stdio" && command.trim().length === 0) {
      setValidationMessage("stdio 模式需要填写 command。");
      commandInputRef.current?.focus();
      return;
    }

    const nextUrl = url.trim();
    if (transport === "http" && nextUrl.length === 0) {
      setValidationMessage("http 模式需要填写 url。");
      urlInputRef.current?.focus();
      return;
    }

    if (transport === "http" && !isValidHttpUrl(nextUrl)) {
      setValidationMessage("请填写有效的 http url。");
      urlInputRef.current?.focus();
      return;
    }

    const parsedEnv = parseKeyValueText("env", envText);
    if (parsedEnv.error) {
      setValidationMessage(parsedEnv.error);
      return;
    }

    const parsedHeaders = parseKeyValueText("headers", headersText);
    if (parsedHeaders.error) {
      setValidationMessage(parsedHeaders.error);
      return;
    }

    const nextArgs = parseArgsText(argsText);

    setValidationMessage(null);

    if (mode === "create") {
      const payload: McpServerCreate = {
        args: nextArgs,
        desired_state: desiredState,
        enabled,
        env: parsedEnv.value,
        headers: parsedHeaders.value,
        name: nextName,
        transport,
      };

      if (transport === "stdio") {
        payload.command = command.trim() || null;
      }

      if (transport === "http") {
        payload.url = nextUrl || null;
      }

      await onCreate(payload);
      return;
    }

    if (!server) {
      return;
    }

    if (
      hasUnsafeRedactedPlaceholder(envText, parsedEnv.value, server.env) ||
      hasUnsafeRedactedPlaceholder(
        headersText,
        parsedHeaders.value,
        server.headers,
      )
    ) {
      setValidationMessage("脱敏值 ******** 需要替换为新值，或保持该区域不变。");
      return;
    }

    const payload: McpServerUpdate = {
      args: nextArgs,
      desired_state: desiredState,
      enabled,
      name: nextName,
    };

    if (!shouldOmitRedactedField(envText, server.env)) {
      payload.env = parsedEnv.value;
    }

    if (!shouldOmitRedactedField(headersText, server.headers)) {
      payload.headers = parsedHeaders.value;
    }

    if (transport === "stdio") {
      payload.command = command.trim() || null;
      payload.url = null;
    }

    if (transport === "http") {
      payload.url = nextUrl || null;
      payload.command = null;
    }

    await onUpdate(server.id, payload);
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-ink/25">
      <div
        aria-labelledby={titleId}
        aria-modal="true"
        className="flex h-full w-full max-w-md flex-col border-l border-hairline bg-canvas shadow-xl"
        ref={drawerRef}
        role="dialog"
      >
        <div className="flex items-center justify-between border-b border-hairline px-4 py-3">
          <h2 className="text-base font-semibold text-ink" id={titleId}>
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

        <form
          className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4"
          noValidate
          onSubmit={(event) => void handleSubmit(event)}
        >
          {validationMessage ? (
            <p
              className="rounded-lg bg-error-soft px-3 py-2 text-xs text-error-deep"
              id={validationId}
              role="alert"
            >
              {validationMessage}
            </p>
          ) : null}
          <div>
            <label className="block text-xs text-body" htmlFor="mcp-form-name">
              服务名称
            </label>
            <input
              className="mt-1 w-full rounded-lg border border-hairline px-3 py-2 text-sm"
              id="mcp-form-name"
              onChange={(event) => {
                setName(event.target.value);
                setValidationMessage(null);
              }}
              required
              ref={nameInputRef}
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
              onChange={(event) => {
                setTransport(event.target.value as McpTransport);
                setValidationMessage(null);
              }}
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
                aria-describedby={validationMessage ? validationId : undefined}
                className="mt-1 w-full rounded-lg border border-hairline px-3 py-2 text-sm"
                id="mcp-form-command"
                onChange={(event) => {
                  setCommand(event.target.value);
                  setValidationMessage(null);
                }}
                ref={commandInputRef}
                required={transport === "stdio"}
                value={command}
              />
            </div>
          ) : (
            <div>
              <label className="block text-xs text-body" htmlFor="mcp-form-url">
                url
              </label>
              <input
                aria-describedby={validationMessage ? validationId : undefined}
                className="mt-1 w-full rounded-lg border border-hairline px-3 py-2 text-sm"
                id="mcp-form-url"
                onChange={(event) => {
                  setUrl(event.target.value);
                  setValidationMessage(null);
                }}
                ref={urlInputRef}
                required={transport === "http"}
                type="url"
                value={url}
              />
            </div>
          )}

          <div>
            <label className="block text-xs text-body" htmlFor="mcp-form-args">
              args
            </label>
            <textarea
              className="mt-1 min-h-20 w-full rounded-lg border border-hairline px-3 py-2 text-sm"
              id="mcp-form-args"
              onChange={(event) => {
                setArgsText(event.target.value);
                setValidationMessage(null);
              }}
              placeholder="每行一个参数"
              value={argsText}
            />
          </div>

          <div>
            <label className="block text-xs text-body" htmlFor="mcp-form-env">
              env
            </label>
            <textarea
              aria-describedby={validationMessage ? validationId : undefined}
              className="mt-1 min-h-20 w-full rounded-lg border border-hairline px-3 py-2 text-sm"
              id="mcp-form-env"
              onChange={(event) => {
                setEnvText(event.target.value);
                setValidationMessage(null);
              }}
              placeholder="KEY=VALUE"
              value={envText}
            />
          </div>

          <div>
            <label className="block text-xs text-body" htmlFor="mcp-form-headers">
              headers
            </label>
            <textarea
              aria-describedby={validationMessage ? validationId : undefined}
              className="mt-1 min-h-20 w-full rounded-lg border border-hairline px-3 py-2 text-sm"
              id="mcp-form-headers"
              onChange={(event) => {
                setHeadersText(event.target.value);
                setValidationMessage(null);
              }}
              placeholder="KEY=VALUE"
              value={headersText}
            />
          </div>

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

function isValidHttpUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

function argsToText(args: string[]): string {
  return args.join("\n");
}

function parseArgsText(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

function keyValueMapToText(value: Record<string, string>): string {
  return Object.entries(value)
    .map(([key, entryValue]) => `${key}=${entryValue}`)
    .join("\n");
}

function parseKeyValueText(
  label: "env" | "headers",
  value: string,
): { error: string | null; value: Record<string, string> } {
  const parsed: Record<string, string> = {};
  const lines = value.split(/\r?\n/);

  for (let index = 0; index < lines.length; index += 1) {
    const rawLine = lines[index] ?? "";
    const line = rawLine.trim();

    if (line.length === 0) {
      continue;
    }

    const separatorIndex = line.indexOf("=");

    if (separatorIndex <= 0) {
      return {
        error: `${label} 第 ${index + 1} 行需要使用 KEY=VALUE 格式。`,
        value: {},
      };
    }

    const key = line.slice(0, separatorIndex).trim();
    const entryValue = line.slice(separatorIndex + 1).trim();

    if (!key) {
      return {
        error: `${label} 第 ${index + 1} 行需要使用 KEY=VALUE 格式。`,
        value: {},
      };
    }

    parsed[key] = entryValue;
  }

  return { error: null, value: parsed };
}

function shouldOmitRedactedField(
  currentText: string,
  original: Record<string, string>,
): boolean {
  return hasRedactedValue(original) && currentText === keyValueMapToText(original);
}

function hasUnsafeRedactedPlaceholder(
  currentText: string,
  parsed: Record<string, string>,
  original: Record<string, string>,
): boolean {
  if (shouldOmitRedactedField(currentText, original)) {
    return false;
  }

  return Object.entries(parsed).some(
    ([key, value]) => value === REDACTED_VALUE && original[key] === REDACTED_VALUE,
  );
}

function hasRedactedValue(value: Record<string, string>): boolean {
  return Object.values(value).some((entryValue) => entryValue === REDACTED_VALUE);
}
