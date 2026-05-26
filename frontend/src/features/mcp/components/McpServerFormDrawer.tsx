import {
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
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
  const [desiredState, setDesiredState] = useState<McpDesiredState>(DEFAULT_DESIRED_STATE);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const drawerRef = useRef<HTMLDivElement | null>(null);
  const nameInputRef = useRef<HTMLInputElement | null>(null);
  const commandInputRef = useRef<HTMLInputElement | null>(null);
  const urlInputRef = useRef<HTMLInputElement | null>(null);
  const titleId = useId();

  // Initialize / reset form state
  useEffect(() => {
    if (!open) return;

    setFieldErrors({});

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
  }, [mode, open, server]);

  // Auto-focus first input
  useEffect(() => {
    if (!open) return;
    nameInputRef.current?.focus();
  }, [open]);

  // Focus trap
  useEffect(() => {
    if (!open) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }

      if (event.key !== "Tab") return;

      const drawerElement = drawerRef.current;
      if (!drawerElement) return;

      const focusableElements = Array.from(
        drawerElement.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      );

      if (focusableElements.length === 0) return;

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
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, open]);

  if (!open) return null;

  function validateForm(): boolean {
    if (!name.trim()) {
      setFieldErrors({ name: "请填写服务名称。" });
      nameInputRef.current?.focus();
      return false;
    }

    if (transport === "stdio" && command.trim().length === 0) {
      setFieldErrors({ command: "stdio 模式需要填写 command。" });
      commandInputRef.current?.focus();
      return false;
    }

    const nextUrl = url.trim();
    if (transport === "http" && nextUrl.length === 0) {
      setFieldErrors({ url: "http 模式需要填写 url。" });
      urlInputRef.current?.focus();
      return false;
    }

    if (transport === "http" && !isValidHttpUrl(nextUrl)) {
      setFieldErrors({ url: "请填写有效的 http url。" });
      urlInputRef.current?.focus();
      return false;
    }

    const parsedEnv = parseKeyValueText("env", envText);
    if (parsedEnv.error) {
      setFieldErrors({ env: parsedEnv.error });
      return false;
    }

    const parsedHeaders = parseKeyValueText("headers", headersText);
    if (parsedHeaders.error) {
      setFieldErrors({ headers: parsedHeaders.error });
      return false;
    }

    setFieldErrors({});
    return true;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!validateForm()) return;

    const parsedEnv = parseKeyValueText("env", envText);
    const parsedHeaders = parseKeyValueText("headers", headersText);
    const nextArgs = parseArgsText(argsText);
    const nextName = name.trim();

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
      } else {
        payload.url = url.trim() || null;
      }

      await onCreate(payload);
      return;
    }

    // Edit mode
    if (!server) return;

    if (
      hasUnsafeRedactedPlaceholder(envText, parsedEnv.value, server.env) ||
      hasUnsafeRedactedPlaceholder(headersText, parsedHeaders.value, server.headers)
    ) {
      setFieldErrors({
        _global: "脱敏值 ******** 需要替换为新值，或保持该区域不变。",
      });
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
    } else {
      payload.url = url.trim() || null;
      payload.command = null;
    }

    await onUpdate(server.id, payload);
  }

  function clearFieldError(field: string) {
    setFieldErrors((prev) => {
      if (!prev[field]) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });
  }

  const hasNameError = !!fieldErrors.name;
  const hasCommandError = !!fieldErrors.command;
  const hasUrlError = !!fieldErrors.url;
  const hasEnvError = !!fieldErrors.env;
  const hasHeadersError = !!fieldErrors.headers;
  const hasGlobalError = !!fieldErrors._global;
  const nameErrorId = useId();
  const commandErrorId = useId();
  const urlErrorId = useId();
  const envErrorId = useId();
  const headersErrorId = useId();
  const globalErrorId = useId();

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-ink/25">
      <div
        aria-labelledby={titleId}
        aria-modal="true"
        className="flex h-full w-full flex-col border-l border-hairline bg-canvas shadow-xl sm:w-[420px]"
        ref={drawerRef}
        role="dialog"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-hairline px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold text-ink" id={titleId}>
              {mode === "create" ? "新增 MCP 服务" : "编辑 MCP 服务"}
            </h2>
            <p className="text-2xs text-mute font-mono">
              {mode === "create" ? "NEW SERVER" : `EDIT · ${server?.id ?? "..."}`}
            </p>
          </div>
          <button
            className="rounded-lg px-2 py-1 text-sm text-mute transition-colors hover:bg-canvas-soft hover:text-ink"
            onClick={onClose}
            type="button"
          >
            关闭
          </button>
        </div>

        {/* Body */}
        <form
          className="min-h-0 flex-1 overflow-y-auto px-4 py-3"
          id="mcp-drawer-form"
          noValidate
          onSubmit={(event) => { void handleSubmit(event); }}
        >
          {/* Global error */}
          {hasGlobalError ? (
            <p
              className="mb-3 rounded-lg bg-error-soft px-3 py-2 text-xs text-error-deep"
              id={globalErrorId}
              role="alert"
            >
              {fieldErrors._global}
            </p>
          ) : null}

          {/* Section: 基本信息 */}
          <SectionHeader>基本信息</SectionHeader>

          <div className="space-y-1">
            <label className="text-xs font-medium text-ink" htmlFor="mcp-form-name">
              服务名称 <span className="text-error">*</span>
            </label>
            <input
              aria-describedby={hasNameError ? nameErrorId : undefined}
              aria-invalid={hasNameError}
              className="h-9 w-full rounded-lg border border-hairline bg-canvas px-3 text-xs text-ink placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 aria-invalid:border-error aria-invalid:ring-error/20"
              id="mcp-form-name"
              onChange={(e) => { setName(e.target.value); clearFieldError("name"); }}
              ref={nameInputRef}
              required
              value={name}
            />
            {hasNameError ? (
              <p className="text-2xs text-error-deep" id={nameErrorId} role="alert">
                {fieldErrors.name}
              </p>
            ) : null}
          </div>

          <div className="mt-3 space-y-1">
            <label className="text-xs font-medium text-ink" htmlFor="mcp-form-transport">
              传输方式
            </label>
            <select
              className="h-9 w-full rounded-lg border border-hairline bg-canvas px-3 text-xs text-ink outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 appearance-none"
              disabled={mode === "edit"}
              id="mcp-form-transport"
              onChange={(e) => setTransport(e.target.value as McpTransport)}
              value={transport}
            >
              <option value="stdio">stdio</option>
              <option value="http">http</option>
            </select>
          </div>

          {/* Section: 连接 */}
          <SectionHeader>连接</SectionHeader>

          {transport === "stdio" ? (
            <>
              <div className="space-y-1">
                <label className="text-xs font-medium text-ink" htmlFor="mcp-form-command">
                  command <span className="text-error">*</span>
                </label>
                <input
                  aria-describedby={hasCommandError ? commandErrorId : undefined}
                  aria-invalid={hasCommandError}
                  className="h-9 w-full rounded-lg border border-hairline bg-canvas px-3 text-xs text-ink placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 aria-invalid:border-error aria-invalid:ring-error/20"
                  id="mcp-form-command"
                  onChange={(e) => { setCommand(e.target.value); clearFieldError("command"); }}
                  ref={commandInputRef}
                  value={command}
                />
                {hasCommandError ? (
                  <p className="text-2xs text-error-deep" id={commandErrorId} role="alert">
                    {fieldErrors.command}
                  </p>
                ) : null}
              </div>
              <div className="mt-3 space-y-1">
                <label className="text-xs font-medium text-ink" htmlFor="mcp-form-args">
                  args
                </label>
                <textarea
                  className="min-h-[72px] w-full rounded-lg border border-hairline bg-canvas px-3 py-2 font-mono text-2xs leading-relaxed text-ink placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 resize-y"
                  id="mcp-form-args"
                  onChange={(e) => setArgsText(e.target.value)}
                  placeholder="每行一个参数"
                  value={argsText}
                />
              </div>
            </>
          ) : (
            <div className="space-y-1">
              <label className="text-xs font-medium text-ink" htmlFor="mcp-form-url">
                url <span className="text-error">*</span>
              </label>
              <input
                aria-describedby={hasUrlError ? urlErrorId : undefined}
                aria-invalid={hasUrlError}
                className="h-9 w-full rounded-lg border border-hairline bg-canvas px-3 text-xs text-ink placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 aria-invalid:border-error aria-invalid:ring-error/20"
                id="mcp-form-url"
                onChange={(e) => { setUrl(e.target.value); clearFieldError("url"); }}
                ref={urlInputRef}
                type="url"
                value={url}
              />
              {hasUrlError ? (
                <p className="text-2xs text-error-deep" id={urlErrorId} role="alert">
                  {fieldErrors.url}
                </p>
              ) : null}
            </div>
          )}

          {/* Section: 环境与请求头 */}
          <SectionHeader>环境与请求头</SectionHeader>

          <div className="space-y-1">
            <label className="text-xs font-medium text-ink" htmlFor="mcp-form-env">
              env
            </label>
            <textarea
              aria-describedby={hasEnvError ? envErrorId : undefined}
              aria-invalid={hasEnvError}
              className="min-h-[72px] w-full rounded-lg border border-hairline bg-canvas px-3 py-2 font-mono text-2xs leading-relaxed text-ink placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 aria-invalid:border-error aria-invalid:ring-error/20 resize-y"
              id="mcp-form-env"
              onChange={(e) => { setEnvText(e.target.value); clearFieldError("env"); }}
              placeholder="KEY=VALUE"
              value={envText}
            />
            {hasEnvError ? (
              <p className="text-2xs text-error-deep" id={envErrorId} role="alert">
                {fieldErrors.env}
              </p>
            ) : null}
          </div>

          <div className="mt-3 space-y-1">
            <label className="text-xs font-medium text-ink" htmlFor="mcp-form-headers">
              headers
            </label>
            <textarea
              aria-describedby={hasHeadersError ? headersErrorId : undefined}
              aria-invalid={hasHeadersError}
              className="min-h-[72px] w-full rounded-lg border border-hairline bg-canvas px-3 py-2 font-mono text-2xs leading-relaxed text-ink placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 aria-invalid:border-error aria-invalid:ring-error/20 resize-y"
              id="mcp-form-headers"
              onChange={(e) => { setHeadersText(e.target.value); clearFieldError("headers"); }}
              placeholder="KEY=VALUE"
              value={headersText}
            />
            {hasHeadersError ? (
              <p className="text-2xs text-error-deep" id={headersErrorId} role="alert">
                {fieldErrors.headers}
              </p>
            ) : null}
          </div>

          {/* Section: 启动行为 */}
          <SectionHeader>启动行为</SectionHeader>

          <label className="flex cursor-pointer items-start gap-2">
            <input
              checked={desiredState === "running"}
              className="mt-0.5 h-4 w-4 rounded border-hairline bg-canvas accent-primary"
              onChange={(e) => setDesiredState(e.target.checked ? "running" : "stopped")}
              type="checkbox"
            />
            <span>
              <span className="text-xs text-ink">创建后立即启动</span>
              <span className="block text-2xs text-mute">
                服务保存后将立即拉起 (desired_state=running)
              </span>
            </span>
          </label>

          <label className="mt-2 flex cursor-pointer items-start gap-2">
            <input
              checked={enabled}
              className="mt-0.5 h-4 w-4 rounded border-hairline bg-canvas accent-primary"
              onChange={(e) => setEnabled(e.target.checked)}
              type="checkbox"
            />
            <span>
              <span className="text-xs text-ink">启用</span>
              <span className="block text-2xs text-mute">
                启用该服务供 agent 使用
              </span>
            </span>
          </label>
        </form>

        {/* Footer */}
        <div className="sticky bottom-0 flex items-center justify-end gap-2 border-t border-hairline bg-canvas px-4 py-3">
          <button
            className="h-9 rounded-lg border border-hairline bg-canvas px-3 text-xs text-body transition-colors hover:border-hairline-strong hover:text-ink"
            onClick={onClose}
            type="button"
          >
            取消
          </button>
          <button
            className="h-9 rounded-lg bg-primary px-3 text-xs font-medium text-on-primary transition-colors hover:bg-primary-deep disabled:cursor-not-allowed disabled:opacity-50"
            disabled={pending}
            form="mcp-drawer-form"
            type="submit"
          >
            {pending ? "提交中..." : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}

function SectionHeader({ children }: { children: ReactNode }) {
  return (
    <h3 className="mt-4 mb-2 border-b border-hairline pb-1.5 text-2xs font-mono uppercase tracking-wide text-mute first:mt-0">
      {children}
    </h3>
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

    if (line.length === 0) continue;

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
  if (shouldOmitRedactedField(currentText, original)) return false;

  return Object.entries(parsed).some(
    ([key, value]) => value === REDACTED_VALUE && original[key] === REDACTED_VALUE,
  );
}

function hasRedactedValue(value: Record<string, string>): boolean {
  return Object.values(value).some((entryValue) => entryValue === REDACTED_VALUE);
}
