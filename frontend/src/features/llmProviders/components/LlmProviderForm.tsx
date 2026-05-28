import {
  cloneElement,
  isValidElement,
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
  type ReactElement,
  type ReactNode,
} from "react";

import { Button } from "../../../components/ui/button";
import type {
  LlmProviderCreate,
  LlmProviderDetail,
  LlmProviderType,
  LlmProviderUpdate,
} from "../types";
import { LLM_PROVIDER_TYPES } from "../types";

const REDACTED_VALUE = "********";

type LlmProviderFormMode = "create" | "edit" | "view";

type LlmProviderFormProps = {
  mode: LlmProviderFormMode;
  provider: LlmProviderDetail | null;
  pending?: boolean;
  onCancel?: () => void;
  onCreate?: (payload: LlmProviderCreate) => Promise<void>;
  onUpdate?: (providerId: string, payload: LlmProviderUpdate) => Promise<void>;
};

export function LlmProviderForm({
  mode,
  provider,
  pending = false,
  onCancel,
  onCreate,
  onUpdate,
}: LlmProviderFormProps) {
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [providerType, setProviderType] = useState("openai");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [clearApiKey, setClearApiKey] = useState(false);
  const [headersText, setHeadersText] = useState("");
  const [queryText, setQueryText] = useState("");
  const [modelsText, setModelsText] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const errorId = useId();
  const displayNameRef = useRef<HTMLInputElement>(null);
  const providerTypeRef = useRef<HTMLSelectElement>(null);
  const headersRef = useRef<HTMLTextAreaElement>(null);
  const queryRef = useRef<HTMLTextAreaElement>(null);
  const initialSnapshotRef = useRef("");
  const readOnly = mode === "view";

  useEffect(() => {
    setError(null);
    setFieldErrors({});
    if ((mode === "edit" || mode === "view") && provider) {
      setDisplayName(provider.display_name);
      setDescription(provider.description ?? "");
      setProviderType(provider.provider_type);
      setBaseUrl(provider.base_url ?? "");
      setApiKey("");
      setClearApiKey(false);
      setHeadersText(keyValueMapToText(provider.default_headers));
      setQueryText(keyValueMapToText(provider.default_query));
      setModelsText(modelsToText(provider.models));
      setEnabled(provider.enabled);
      initialSnapshotRef.current = snapshotForm({
        apiKey: "",
        baseUrl: provider.base_url ?? "",
        clearApiKey: false,
        description: provider.description ?? "",
        displayName: provider.display_name,
        enabled: provider.enabled,
        headersText: keyValueMapToText(provider.default_headers),
        modelsText: modelsToText(provider.models),
        providerType: provider.provider_type,
        queryText: keyValueMapToText(provider.default_query),
      });
      return;
    }

    setDisplayName("");
    setDescription("");
    setProviderType("openai");
    setBaseUrl("");
    setApiKey("");
    setClearApiKey(false);
    setHeadersText("");
    setQueryText("");
    setModelsText("");
    setEnabled(true);
    initialSnapshotRef.current = snapshotForm({
      apiKey: "",
      baseUrl: "",
      clearApiKey: false,
      description: "",
      displayName: "",
      enabled: true,
      headersText: "",
      modelsText: "",
      providerType: "openai",
      queryText: "",
    });
  }, [mode, provider]);

  const currentSnapshot = snapshotForm({
    apiKey,
    baseUrl,
    clearApiKey,
    description,
    displayName,
    enabled,
    headersText,
    modelsText,
    providerType,
    queryText,
  });
  const dirty = !readOnly && currentSnapshot !== initialSnapshotRef.current;

  useEffect(() => {
    if (!dirty) return;
    function handleBeforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault();
    }
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [dirty]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (readOnly) return;
    setFieldErrors({});

    const parsedHeaders = parseKeyValueText("Default Headers", headersText);
    if (parsedHeaders.error) {
      setFieldErrors({ defaultHeaders: parsedHeaders.error });
      setError(parsedHeaders.error);
      headersRef.current?.focus();
      return;
    }

    const parsedQuery = parseKeyValueText("Default Query", queryText);
    if (parsedQuery.error) {
      setFieldErrors({ defaultQuery: parsedQuery.error });
      setError(parsedQuery.error);
      queryRef.current?.focus();
      return;
    }
    const models = parseModelsText(modelsText);

    if (!displayName.trim()) {
      const message = "Display Name 必填。";
      setFieldErrors({ displayName: message });
      setError(message);
      displayNameRef.current?.focus();
      return;
    }

    if (!isSupportedProviderType(providerType)) {
      const message = "Provider Type 不在当前 init_chat_model 支持列表中，请重新选择。";
      setFieldErrors({ providerType: message });
      setError(message);
      providerTypeRef.current?.focus();
      return;
    }

    setError(null);
    const supportedProviderType = providerType as LlmProviderType;

    if (mode === "create") {
      await onCreate?.({
        api_key: apiKey.trim() || null,
        base_url: baseUrl.trim() || null,
        default_headers: parsedHeaders.value,
        default_query: parsedQuery.value,
        description: description.trim() || null,
        display_name: displayName.trim(),
        enabled,
        models,
        provider_type: supportedProviderType,
      });
      initialSnapshotRef.current = currentSnapshot;
      return;
    }

    if (!provider) return;
    const payload: LlmProviderUpdate = {
      base_url: baseUrl.trim() || null,
      description: description.trim() || null,
      display_name: displayName.trim(),
      enabled,
      models,
      provider_type: supportedProviderType,
    };
    const shouldOmitHeaders = shouldOmitRedactedField(
      headersText,
      provider.default_headers,
    );
    const shouldOmitQuery = shouldOmitRedactedField(
      queryText,
      provider.default_query,
    );
    if (
      hasUnsafeRedactedPlaceholder(
        headersText,
        parsedHeaders.value,
        provider.default_headers,
      ) ||
      hasUnsafeRedactedPlaceholder(
        queryText,
        parsedQuery.value,
        provider.default_query,
      )
    ) {
      setError("脱敏值 ******** 需要替换为新值，或保持该区域不变。");
      headersRef.current?.focus();
      return;
    }
    if (!shouldOmitHeaders) {
      payload.default_headers = parsedHeaders.value;
    }
    if (!shouldOmitQuery) {
      payload.default_query = parsedQuery.value;
    }
    if (apiKey.trim()) {
      payload.api_key = apiKey.trim();
    } else if (clearApiKey) {
      payload.api_key = null;
    }
    await onUpdate?.(provider.id, payload);
    initialSnapshotRef.current = currentSnapshot;
  }

  function handleCancel() {
    if (dirty && !window.confirm("有未保存的修改，确认离开？")) return;
    onCancel?.();
  }

  const inputClass =
    "h-10 w-full rounded-xl border border-hairline bg-canvas px-3 text-sm text-ink shadow-sm shadow-primary/0 placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 read-only:bg-canvas-soft/70 read-only:text-body disabled:bg-canvas-soft disabled:text-body";
  const textAreaClass =
    "min-h-[110px] w-full resize-y rounded-xl border border-hairline bg-canvas px-3 py-2.5 font-mono text-sm leading-relaxed text-ink shadow-sm shadow-primary/0 placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 read-only:bg-canvas-soft/70 read-only:text-body";

  return (
    <section className="overflow-hidden rounded-3xl border border-primary/10 bg-canvas/95 shadow-[0_18px_50px_rgba(0,100,224,0.08)]">
      <form className="space-y-4 p-4 sm:p-5" noValidate onSubmit={(event) => { void handleSubmit(event); }}>
        {error ? (
          <p className="rounded-lg bg-error-soft px-3 py-2 text-xs text-error-deep" id={errorId} role="alert">
            {error}
          </p>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-2">
          <Field error={fieldErrors.displayName} label="Display Name" required={!readOnly}>
            <input
              className={inputClass}
              autoComplete="off"
              aria-invalid={Boolean(fieldErrors.displayName)}
              onChange={(event) => setDisplayName(event.target.value)}
              name="display_name"
              readOnly={readOnly}
              ref={displayNameRef}
              value={displayName}
            />
          </Field>
          <Field error={fieldErrors.providerType} label="Provider Type" required={!readOnly}>
            <select
              className={inputClass}
              disabled={readOnly}
              aria-invalid={Boolean(fieldErrors.providerType)}
              onChange={(event) => setProviderType(event.target.value)}
              name="provider_type"
              ref={providerTypeRef}
              value={providerType}
            >
              {!isSupportedProviderType(providerType) ? (
                <option value={providerType}>{providerType} (unsupported)</option>
              ) : null}
              {LLM_PROVIDER_TYPES.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Base URL">
            <input
              className={inputClass}
              autoComplete="off"
              onChange={(event) => setBaseUrl(event.target.value)}
              name="base_url"
              placeholder="https://api.openai.com/v1"
              readOnly={readOnly}
              type="url"
              value={baseUrl}
            />
          </Field>
        </div>

        <Field label="Description">
          <textarea
            className={textAreaClass}
            name="description"
            onChange={(event) => setDescription(event.target.value)}
            readOnly={readOnly}
            value={description}
          />
        </Field>

        {mode !== "view" ? (
          <div className="rounded-2xl border border-hairline bg-canvas-soft/50 p-3">
            <Field label="API Key">
              <input
                className={inputClass}
                autoComplete="new-password"
                onChange={(event) => setApiKey(event.target.value)}
                name="api_key"
                placeholder={mode === "edit" ? "留空表示保留现有 API Key" : "sk-..."}
                type="password"
                value={apiKey}
              />
            </Field>
            {mode === "edit" ? (
              <label className="mt-2 flex items-center gap-2 text-xs text-body">
                <input
                  checked={clearApiKey}
                  className="h-4 w-4 rounded border-hairline text-primary"
                  onChange={(event) => setClearApiKey(event.target.checked)}
                  type="checkbox"
                />
                清除现有 API Key
              </label>
            ) : null}
            {mode === "edit" ? (
              <p className="mt-2 text-xs text-mute">
                留空表示保留现有 API Key；勾选清除会发送 null。
              </p>
            ) : null}
          </div>
        ) : (
          <p className="rounded-2xl border border-hairline bg-canvas-soft/60 px-3 py-2 text-xs text-body">
            API Key：{provider?.api_key_configured ? "已配置" : "未配置"}
          </p>
        )}

        <div className="grid gap-3 lg:grid-cols-2">
          <Field error={fieldErrors.defaultHeaders} label="Default Headers">
            <textarea
              className={textAreaClass}
              aria-invalid={Boolean(fieldErrors.defaultHeaders)}
              name="default_headers"
              onChange={(event) => setHeadersText(event.target.value)}
              placeholder="X-Tenant=quality"
              readOnly={readOnly}
              ref={headersRef}
              spellCheck={false}
              value={headersText}
            />
          </Field>
          <Field error={fieldErrors.defaultQuery} label="Default Query">
            <textarea
              className={textAreaClass}
              aria-invalid={Boolean(fieldErrors.defaultQuery)}
              name="default_query"
              onChange={(event) => setQueryText(event.target.value)}
              placeholder="api-version=2026-01-01"
              readOnly={readOnly}
              ref={queryRef}
              spellCheck={false}
              value={queryText}
            />
          </Field>
        </div>

        <Field label="Models">
          <textarea
            className={textAreaClass}
            name="models"
            onChange={(event) => setModelsText(event.target.value)}
            placeholder={"gpt-5-mini\ngpt-5"}
            readOnly={readOnly}
            spellCheck={false}
            value={modelsText}
          />
        </Field>

        <label className="flex items-center gap-2 text-xs text-body">
          <input
            checked={enabled}
            className="h-4 w-4 rounded border-hairline text-primary"
            disabled={readOnly}
            onChange={(event) => setEnabled(event.target.checked)}
            type="checkbox"
          />
          启用 Provider
        </label>

        {mode !== "view" ? (
          <div className="flex justify-end gap-2 border-t border-hairline pt-4">
            {onCancel ? (
              <Button onClick={handleCancel} type="button" variant="secondary">
                取消
              </Button>
            ) : null}
            <Button aria-busy={pending} disabled={pending} type="submit" variant="primary">
              {pending ? "保存中…" : "保存 Provider"}
            </Button>
          </div>
        ) : null}
      </form>
    </section>
  );
}

function FieldError({ message }: { message: string }) {
  return <p className="text-xs text-error-deep">{message}</p>;
}

function Field({
  children,
  error,
  label,
  required = false,
}: {
  children: ReactNode;
  error?: string;
  label: string;
  required?: boolean;
}) {
  const id = useId();
  return (
    <div className="space-y-1">
      <label className="text-sm font-medium text-ink" htmlFor={id}>
        {label} {required ? <span className="text-error">*</span> : null}
      </label>
      <div className="[&>input]:w-full [&>select]:w-full [&>textarea]:w-full">
        {cloneWithId(children, id)}
      </div>
      {error ? <FieldError message={error} /> : null}
    </div>
  );
}

function cloneWithId(children: ReactNode, id: string) {
  if (!isValidElement(children)) return children;
  return cloneElement(children as ReactElement<{ id?: string }>, { id });
}

export function keyValueMapToText(value: Record<string, string>): string {
  return Object.entries(value)
    .map(([key, item]) => `${key}=${item}`)
    .join("\n");
}

export function parseKeyValueText(label: string, text: string) {
  const value: Record<string, string> = {};
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    const separatorIndex = line.indexOf("=");
    if (separatorIndex <= 0) {
      return { error: `${label} 需要使用 KEY=VALUE 格式。`, value };
    }
    const key = line.slice(0, separatorIndex).trim();
    const item = line.slice(separatorIndex + 1).trim();
    if (!key) {
      return { error: `${label} 存在空 key。`, value };
    }
    value[key] = item;
  }
  return { error: null, value };
}

export function modelsToText(value: string[]): string {
  return value.join("\n");
}

export function parseModelsText(text: string): string[] {
  const models: string[] = [];
  const seen = new Set<string>();
  for (const rawLine of text.split(/\r?\n/)) {
    const model = rawLine.trim();
    if (!model || seen.has(model)) continue;
    models.push(model);
    seen.add(model);
  }
  return models;
}

function shouldOmitRedactedField(
  text: string,
  currentValue: Record<string, string>,
): boolean {
  return (
    Object.values(currentValue).includes(REDACTED_VALUE) &&
    text === keyValueMapToText(currentValue)
  );
}

function hasUnsafeRedactedPlaceholder(
  text: string,
  parsedValue: Record<string, string>,
  currentValue: Record<string, string>,
): boolean {
  return (
    Object.values(parsedValue).includes(REDACTED_VALUE) &&
    !shouldOmitRedactedField(text, currentValue)
  );
}

function toSupportedProviderType(value: string): LlmProviderType {
  if (isSupportedProviderType(value)) {
    return value as LlmProviderType;
  }
  return "openai";
}

function isSupportedProviderType(value: string): value is LlmProviderType {
  return (LLM_PROVIDER_TYPES as readonly string[]).includes(value);
}

function snapshotForm(value: {
  apiKey: string;
  baseUrl: string;
  clearApiKey: boolean;
  description: string;
  displayName: string;
  enabled: boolean;
  headersText: string;
  modelsText: string;
  providerType: string;
  queryText: string;
}): string {
  return JSON.stringify(value);
}
