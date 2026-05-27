import {
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";

import { Button } from "../../../components/ui/button";
import { Select } from "../../../components/ui/select";
import type {
  McpDesiredState,
  McpServerCreate,
  McpServerDetail,
  McpServerUpdate,
  McpTransport,
} from "../types";

type McpServerFormMode = "create" | "edit" | "view";

type McpServerFormProps = {
  mode: McpServerFormMode;
  server: McpServerDetail | null;
  pending?: boolean;
  onCancel?: () => void;
  onCreate?: (payload: McpServerCreate) => Promise<void>;
  onUpdate?: (serverId: string, payload: McpServerUpdate) => Promise<void>;
};

const DEFAULT_TRANSPORT: McpTransport = "stdio";
const DEFAULT_DESIRED_STATE: McpDesiredState = "stopped";
const DEFAULT_ENABLED = false;
const REDACTED_VALUE = "********";

export function McpServerForm({
  mode,
  server,
  pending = false,
  onCancel,
  onCreate,
  onUpdate,
}: McpServerFormProps) {
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

  const nameInputRef = useRef<HTMLInputElement | null>(null);
  const commandInputRef = useRef<HTMLInputElement | null>(null);
  const urlInputRef = useRef<HTMLInputElement | null>(null);
  const formId = useId();
  const nameErrorId = useId();
  const commandErrorId = useId();
  const urlErrorId = useId();
  const envErrorId = useId();
  const headersErrorId = useId();
  const globalErrorId = useId();

  const readOnly = mode === "view";
  const canSubmit = mode !== "view";

  useEffect(() => {
    setFieldErrors({});

    if ((mode === "edit" || mode === "view") && server) {
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
  }, [mode, server]);

  useEffect(() => {
    if (mode === "create") {
      nameInputRef.current?.focus();
    }
  }, [mode]);

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

    if (readOnly || !validateForm()) return;

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

      await onCreate?.(payload);
      return;
    }

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

    await onUpdate?.(server.id, payload);
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
  const inputClass =
    "h-9 w-full rounded-xl border border-hairline bg-canvas px-3 text-xs text-ink shadow-sm shadow-primary/0 placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 read-only:bg-canvas-soft/70 read-only:text-body disabled:bg-canvas-soft disabled:text-body aria-invalid:border-error aria-invalid:ring-error/20";
  const textAreaClass =
    "min-h-[92px] w-full rounded-xl border border-hairline bg-canvas px-3 py-2 font-mono text-2xs leading-relaxed text-ink shadow-sm shadow-primary/0 placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 read-only:bg-canvas-soft/70 read-only:text-body disabled:bg-canvas-soft disabled:text-body aria-invalid:border-error aria-invalid:ring-error/20 resize-y";
  const argsTextAreaClass =
    "min-h-[132px] w-full rounded-xl border border-hairline bg-canvas px-3 py-2 font-mono text-2xs leading-relaxed text-ink shadow-sm shadow-primary/0 placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 read-only:bg-canvas-soft/70 read-only:text-body disabled:bg-canvas-soft disabled:text-body aria-invalid:border-error aria-invalid:ring-error/20 resize-y";

  return (
    <section
      aria-label="配置工作区"
      className="overflow-hidden rounded-3xl border border-primary/10 bg-canvas/95 shadow-[0_18px_50px_rgba(0,100,224,0.08)]"
    >
      <form
        className="space-y-4 p-4 sm:p-5"
        id={formId}
        noValidate
        onSubmit={(event) => { void handleSubmit(event); }}
      >
        {hasGlobalError ? (
          <p
            className="mb-3 rounded-lg bg-error-soft px-3 py-2 text-xs text-error-deep"
            id={globalErrorId}
            role="alert"
          >
            {fieldErrors._global}
          </p>
        ) : null}

        <ConfigSection
          description="命名和 transport 是 server 的识别层；transport 创建后不可切换。"
          eyebrow="Identity"
          title="基本信息"
        >
          <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_180px]">
            <div className="space-y-1">
              <label className="text-xs font-medium text-ink" htmlFor="mcp-form-name">
                服务名称 {canSubmit ? <span className="text-error">*</span> : null}
              </label>
              <input
                aria-describedby={hasNameError ? nameErrorId : undefined}
                aria-invalid={hasNameError}
                className={inputClass}
                id="mcp-form-name"
                onChange={(e) => { setName(e.target.value); clearFieldError("name"); }}
                readOnly={readOnly}
                ref={nameInputRef}
                required={canSubmit}
                value={name}
              />
              {hasNameError ? (
                <p className="text-2xs text-error-deep" id={nameErrorId} role="alert">
                  {fieldErrors.name}
                </p>
              ) : null}
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-ink" htmlFor="mcp-form-transport">
                传输方式
              </label>
              <Select
                aria-label="传输方式"
                className="w-full"
                disabled={mode !== "create"}
                id="mcp-form-transport"
                onChange={(e) => setTransport(e.target.value as McpTransport)}
                value={transport}
              >
                <option value="stdio">stdio</option>
                <option value="http">http</option>
              </Select>
            </div>
          </div>
        </ConfigSection>

        <ConfigSection
          description={transport === "stdio" ? "stdio server 由本地 command 启动，args 每行一个。" : "http server 使用远端 URL 建立连接。"}
          eyebrow="Connection"
          title="连接"
        >
          {transport === "stdio" ? (
            <div className="grid gap-3 sm:grid-cols-[220px_minmax(0,1fr)] lg:grid-cols-[260px_minmax(0,1fr)]">
              <div className="space-y-1">
                <label className="text-xs font-medium text-ink" htmlFor="mcp-form-command">
                  command {canSubmit ? <span className="text-error">*</span> : null}
                </label>
                <input
                  aria-describedby={hasCommandError ? commandErrorId : undefined}
                  aria-invalid={hasCommandError}
                  className={inputClass}
                  id="mcp-form-command"
                  onChange={(e) => { setCommand(e.target.value); clearFieldError("command"); }}
                  readOnly={readOnly}
                  ref={commandInputRef}
                  value={command}
                />
                {hasCommandError ? (
                  <p className="text-2xs text-error-deep" id={commandErrorId} role="alert">
                    {fieldErrors.command}
                  </p>
                ) : null}
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-ink" htmlFor="mcp-form-args">
                  args
                </label>
                <textarea
                  className={argsTextAreaClass}
                  id="mcp-form-args"
                  onChange={(e) => setArgsText(e.target.value)}
                  placeholder="每行一个参数"
                  readOnly={readOnly}
                  value={argsText}
                />
              </div>
            </div>
          ) : (
            <div className="space-y-1">
              <label className="text-xs font-medium text-ink" htmlFor="mcp-form-url">
                url {canSubmit ? <span className="text-error">*</span> : null}
              </label>
              <input
                aria-describedby={hasUrlError ? urlErrorId : undefined}
                aria-invalid={hasUrlError}
                className={inputClass}
                id="mcp-form-url"
                onChange={(e) => { setUrl(e.target.value); clearFieldError("url"); }}
                readOnly={readOnly}
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
        </ConfigSection>

        <ConfigSection
          description="密钥与请求头使用 KEY=VALUE。编辑时保留脱敏值不会覆盖原值。"
          eyebrow="Secrets"
          title="环境与请求头"
        >
          <div className="grid gap-3 lg:grid-cols-2">
            <div className="space-y-1">
              <label className="text-xs font-medium text-ink" htmlFor="mcp-form-env">
                env
              </label>
              <textarea
                aria-describedby={hasEnvError ? envErrorId : undefined}
                aria-invalid={hasEnvError}
                className={textAreaClass}
                id="mcp-form-env"
                onChange={(e) => { setEnvText(e.target.value); clearFieldError("env"); }}
                placeholder="KEY=VALUE"
                readOnly={readOnly}
                value={envText}
              />
              {hasEnvError ? (
                <p className="text-2xs text-error-deep" id={envErrorId} role="alert">
                  {fieldErrors.env}
                </p>
              ) : null}
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-ink" htmlFor="mcp-form-headers">
                headers
              </label>
              <textarea
                aria-describedby={hasHeadersError ? headersErrorId : undefined}
                aria-invalid={hasHeadersError}
                className={textAreaClass}
                id="mcp-form-headers"
                onChange={(e) => { setHeadersText(e.target.value); clearFieldError("headers"); }}
                placeholder="KEY=VALUE"
                readOnly={readOnly}
                value={headersText}
              />
              {hasHeadersError ? (
                <p className="text-2xs text-error-deep" id={headersErrorId} role="alert">
                  {fieldErrors.headers}
                </p>
              ) : null}
            </div>
          </div>
        </ConfigSection>

        <ConfigSection
          description="保存配置和是否对 agent 暴露是两件事，默认先安全落盘。"
          eyebrow="Lifecycle"
          title="启动行为"
        >
          <div className="grid gap-2 sm:grid-cols-2">
            <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-hairline bg-canvas-soft/70 px-3 py-3 transition-colors hover:border-primary/30">
              <input
                checked={desiredState === "running"}
                className="mt-0.5 h-4 w-4 rounded border-hairline bg-canvas accent-primary disabled:opacity-60"
                disabled={readOnly}
                onChange={(e) => setDesiredState(e.target.checked ? "running" : "stopped")}
                type="checkbox"
              />
              <span>
                <span className="text-xs font-medium text-ink">创建后立即启动</span>
                <span className="block font-mono text-2xs text-mute">
                  desired_state={desiredState}
                </span>
              </span>
            </label>

            <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-hairline bg-canvas-soft/70 px-3 py-3 transition-colors hover:border-primary/30">
              <input
                checked={enabled}
                className="mt-0.5 h-4 w-4 rounded border-hairline bg-canvas accent-primary disabled:opacity-60"
                disabled={readOnly}
                onChange={(e) => setEnabled(e.target.checked)}
                type="checkbox"
              />
              <span>
                <span className="text-xs font-medium text-ink">启用</span>
                <span className="block text-2xs text-mute">
                  {enabled ? "可供 agent 使用" : "暂不供 agent 使用"}
                </span>
              </span>
            </label>
          </div>
        </ConfigSection>
      </form>

      {canSubmit ? (
        <div className="flex items-center justify-end gap-2 border-t border-primary/10 bg-canvas/90 px-4 py-3">
          {onCancel ? (
            <Button
              onClick={onCancel}
              variant="secondary"
            >
              取消
            </Button>
          ) : null}
          <Button
            disabled={pending}
            form={formId}
            type="submit"
            variant="primary"
          >
            {pending ? "提交中..." : "保存"}
          </Button>
        </div>
      ) : null}
    </section>
  );
}

function ConfigSection({
  children,
  description,
  eyebrow,
  title,
}: {
  children: ReactNode;
  description: string;
  eyebrow: string;
  title: string;
}) {
  return (
    <section className="rounded-2xl border border-hairline bg-canvas px-4 py-4">
      <div className="mb-3 flex flex-col gap-1">
        <p className="font-mono text-2xs uppercase tracking-[0.16em] text-primary-deep">
          {eyebrow}
        </p>
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        <p className="max-w-2xl text-xs leading-relaxed text-body">{description}</p>
      </div>
      {children}
    </section>
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
