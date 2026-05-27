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
  LlmProviderUpdate,
} from "../types";

const REDACTED_VALUE = "********";

type LlmProviderFormMode = "create" | "edit" | "view";

type LlmProviderFormProps = {
  mode: LlmProviderFormMode;
  provider: LlmProviderDetail | null;
  pending?: boolean;
  onCancel?: () => void;
  onCreate?: (payload: LlmProviderCreate) => Promise<void>;
  onUpdate?: (providerKey: string, payload: LlmProviderUpdate) => Promise<void>;
};

export function LlmProviderForm({
  mode,
  provider,
  pending = false,
  onCancel,
  onCreate,
  onUpdate,
}: LlmProviderFormProps) {
  const [key, setKey] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [providerType, setProviderType] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [clearApiKey, setClearApiKey] = useState(false);
  const [headersText, setHeadersText] = useState("");
  const [queryText, setQueryText] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const keyRef = useRef<HTMLInputElement | null>(null);
  const errorId = useId();
  const readOnly = mode === "view";

  useEffect(() => {
    setError(null);
    if ((mode === "edit" || mode === "view") && provider) {
      setKey(provider.key);
      setDisplayName(provider.display_name);
      setDescription(provider.description ?? "");
      setProviderType(provider.provider_type);
      setBaseUrl(provider.base_url ?? "");
      setApiKey("");
      setClearApiKey(false);
      setHeadersText(keyValueMapToText(provider.default_headers));
      setQueryText(keyValueMapToText(provider.default_query));
      setEnabled(provider.enabled);
      return;
    }

    setKey("");
    setDisplayName("");
    setDescription("");
    setProviderType("");
    setBaseUrl("");
    setApiKey("");
    setClearApiKey(false);
    setHeadersText("");
    setQueryText("");
    setEnabled(true);
  }, [mode, provider]);

  useEffect(() => {
    if (mode === "create") {
      keyRef.current?.focus();
    }
  }, [mode]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (readOnly) return;

    const parsedHeaders = parseKeyValueText("Default Headers", headersText);
    if (parsedHeaders.error) {
      setError(parsedHeaders.error);
      return;
    }

    const parsedQuery = parseKeyValueText("Default Query", queryText);
    if (parsedQuery.error) {
      setError(parsedQuery.error);
      return;
    }

    if (!key.trim()) {
      setError("Provider Key 必填。");
      keyRef.current?.focus();
      return;
    }

    if (!displayName.trim()) {
      setError("Display Name 必填。");
      return;
    }

    if (!providerType.trim()) {
      setError("Provider Type 必填。");
      return;
    }

    setError(null);

    if (mode === "create") {
      await onCreate?.({
        api_key: apiKey.trim() || null,
        base_url: baseUrl.trim() || null,
        default_headers: parsedHeaders.value,
        default_query: parsedQuery.value,
        description: description.trim() || null,
        display_name: displayName.trim(),
        enabled,
        key: key.trim(),
        provider_type: providerType.trim(),
      });
      return;
    }

    if (!provider) return;
    const payload: LlmProviderUpdate = {
      base_url: baseUrl.trim() || null,
      description: description.trim() || null,
      display_name: displayName.trim(),
      enabled,
      provider_type: providerType.trim(),
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
    await onUpdate?.(provider.key, payload);
  }

  const inputClass =
    "h-9 w-full rounded-xl border border-hairline bg-canvas px-3 text-xs text-ink shadow-sm shadow-primary/0 placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 read-only:bg-canvas-soft/70 read-only:text-body disabled:bg-canvas-soft disabled:text-body";
  const textAreaClass =
    "min-h-[92px] w-full resize-y rounded-xl border border-hairline bg-canvas px-3 py-2 font-mono text-2xs leading-relaxed text-ink shadow-sm shadow-primary/0 placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 read-only:bg-canvas-soft/70 read-only:text-body";

  return (
    <section className="overflow-hidden rounded-3xl border border-primary/10 bg-canvas/95 shadow-[0_18px_50px_rgba(0,100,224,0.08)]">
      <form className="space-y-4 p-4 sm:p-5" noValidate onSubmit={(event) => { void handleSubmit(event); }}>
        {error ? (
          <p className="rounded-lg bg-error-soft px-3 py-2 text-xs text-error-deep" id={errorId} role="alert">
            {error}
          </p>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Provider Key" required={mode === "create"}>
            <input
              aria-describedby={error ? errorId : undefined}
              className={inputClass}
              onChange={(event) => setKey(event.target.value)}
              readOnly={readOnly || mode !== "create"}
              ref={keyRef}
              value={key}
            />
          </Field>
          <Field label="Display Name" required={!readOnly}>
            <input
              className={inputClass}
              onChange={(event) => setDisplayName(event.target.value)}
              readOnly={readOnly}
              value={displayName}
            />
          </Field>
          <Field label="Provider Type" required={!readOnly}>
            <input
              className={inputClass}
              onChange={(event) => setProviderType(event.target.value)}
              placeholder="openai"
              readOnly={readOnly}
              value={providerType}
            />
          </Field>
          <Field label="Base URL">
            <input
              className={inputClass}
              onChange={(event) => setBaseUrl(event.target.value)}
              placeholder="https://api.openai.com/v1"
              readOnly={readOnly}
              value={baseUrl}
            />
          </Field>
        </div>

        <Field label="Description">
          <textarea
            className={textAreaClass}
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
                onChange={(event) => setApiKey(event.target.value)}
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
              <p className="mt-2 text-2xs text-mute">
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
          <Field label="Default Headers">
            <textarea
              className={textAreaClass}
              onChange={(event) => setHeadersText(event.target.value)}
              placeholder="X-Tenant=quality"
              readOnly={readOnly}
              value={headersText}
            />
          </Field>
          <Field label="Default Query">
            <textarea
              className={textAreaClass}
              onChange={(event) => setQueryText(event.target.value)}
              placeholder="api-version=2026-01-01"
              readOnly={readOnly}
              value={queryText}
            />
          </Field>
        </div>

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
              <Button onClick={onCancel} type="button" variant="secondary">
                取消
              </Button>
            ) : null}
            <Button disabled={pending} type="submit" variant="primary">
              保存 Provider
            </Button>
          </div>
        ) : null}
      </form>
    </section>
  );
}

function Field({
  children,
  label,
  required = false,
}: {
  children: ReactNode;
  label: string;
  required?: boolean;
}) {
  const id = useId();
  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-ink" htmlFor={id}>
        {label} {required ? <span className="text-error">*</span> : null}
      </label>
      <div className="[&>input]:w-full [&>textarea]:w-full">
        {cloneWithId(children, id)}
      </div>
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
