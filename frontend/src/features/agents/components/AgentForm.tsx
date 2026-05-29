import {
  cloneElement,
  isValidElement,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type ReactElement,
  type ReactNode,
} from "react";

import { Button } from "../../../components/ui/button";
import { StreamMarkdown } from "../../sop-quality-checks/components/StreamMarkdown";
import type { LlmProviderSummary } from "../../llmProviders/types";
import type {
  AgentCreate,
  AgentDetail,
  AgentDraftConfig,
  AgentDraftUpdate,
} from "../types";
import { CODEAGENT_MODEL_OPTIONS } from "../types";

type AgentFormMode = "create" | "edit";
type ModelSource = "codeagent" | "provider";

type AgentFormProps = {
  mode: AgentFormMode;
  agent: AgentDetail | null;
  providers: LlmProviderSummary[];
  providersLoading: boolean;
  pending?: boolean;
  onCancel?: () => void;
  onCreate?: (payload: AgentCreate) => Promise<void>;
  onUpdate?: (agentId: string, payload: AgentDraftUpdate) => Promise<void>;
};

const DEFAULT_CODEAGENT_MODEL = CODEAGENT_MODEL_OPTIONS[0];
const DEFAULT_SYSTEM_PROMPT =
  "你是谨慎的变更质量评审助手。请基于事实审查输入内容，指出风险、缺口和可执行的整改建议。";

type FieldErrorKey = "display_name" | "system_prompt";

export function AgentForm({
  mode,
  agent,
  providers,
  providersLoading,
  pending = false,
  onCancel,
  onCreate,
  onUpdate,
}: AgentFormProps) {
  const enabledProviders = useMemo(
    () => providers.filter((provider) => provider.enabled),
    [providers],
  );
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState(DEFAULT_SYSTEM_PROMPT);
  const [modelSource, setModelSource] = useState<ModelSource>("codeagent");
  const [codeAgentModel, setCodeAgentModel] = useState<string>(
    DEFAULT_CODEAGENT_MODEL,
  );
  const [selectedProviderId, setSelectedProviderId] = useState("");
  const [selectedProviderModel, setSelectedProviderModel] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [errorField, setErrorField] = useState<FieldErrorKey | null>(null);
  const [systemPromptView, setSystemPromptView] = useState<"edit" | "preview">(
    mode === "edit" ? "preview" : "edit",
  );
  const displayNameRef = useRef<HTMLInputElement>(null);
  const systemPromptRef = useRef<HTMLTextAreaElement>(null);
  const errorId = useId();
  const systemPromptId = useId();

  useEffect(() => {
    if (errorField === "system_prompt" && systemPromptView === "edit") {
      systemPromptRef.current?.focus();
    }
  }, [errorField, systemPromptView]);

  useEffect(() => {
    setError(null);
    setErrorField(null);

    if (mode === "edit" && agent) {
      const draft = agent.draft;
      setDisplayName(agent.display_name);
      setDescription(agent.description ?? "");
      setSystemPrompt(draft?.system_prompt ?? "");
      setEnabled(agent.enabled);
      setModelSource(draft?.provider_id ? "provider" : "codeagent");
      setCodeAgentModel(
        draft?.provider_id
          ? DEFAULT_CODEAGENT_MODEL
          : (draft?.model ?? DEFAULT_CODEAGENT_MODEL),
      );
      setSelectedProviderId(draft?.provider_id ?? "");
      setSelectedProviderModel(draft?.provider_id ? (draft?.model ?? "") : "");
      return;
    }

    setDisplayName("");
    setDescription("");
    setSystemPrompt(DEFAULT_SYSTEM_PROMPT);
    setEnabled(true);
    setModelSource("codeagent");
    setCodeAgentModel(DEFAULT_CODEAGENT_MODEL);
    setSelectedProviderId("");
    setSelectedProviderModel("");
  }, [agent, mode]);

  useEffect(() => {
    if (modelSource !== "provider" || enabledProviders.length === 0) return;
    if (selectedProviderId) return;
    setSelectedProviderId(enabledProviders[0]?.id ?? "");
  }, [enabledProviders, modelSource, selectedProviderId]);

  const selectedProvider = enabledProviders.find(
    (provider) => provider.id === selectedProviderId,
  );
  const selectedProviderModels = selectedProvider?.models ?? [];
  const unavailableCodeAgentModel =
    mode === "edit" &&
    modelSource === "codeagent" &&
    Boolean(codeAgentModel) &&
    !(CODEAGENT_MODEL_OPTIONS as readonly string[]).includes(codeAgentModel);
  const unavailableDraftProvider =
    mode === "edit" &&
    modelSource === "provider" &&
    !providersLoading &&
    Boolean(selectedProviderId) &&
    !selectedProvider;
  const unavailableProviderModel =
    mode === "edit" &&
    modelSource === "provider" &&
    Boolean(selectedProvider) &&
    Boolean(selectedProviderModel) &&
    selectedProviderModels.length > 0 &&
    !selectedProviderModels.includes(selectedProviderModel);

  useEffect(() => {
    if (modelSource !== "provider" || !selectedProvider) return;
    if (selectedProvider.models.length === 0) return;
    if (selectedProviderModel) return;
    setSelectedProviderModel(selectedProvider.models[0] ?? "");
  }, [modelSource, selectedProvider, selectedProviderModel]);

  const providerSaveBlocked =
    modelSource === "provider" &&
    (providersLoading ||
      unavailableDraftProvider ||
      !selectedProvider ||
      selectedProviderModels.length === 0);
  const showUnavailableProviderMessage = unavailableDraftProvider;
  const modelSaveBlocked = unavailableCodeAgentModel || unavailableProviderModel;
  const saveBlocked = providerSaveBlocked || modelSaveBlocked;
  const showProviderModelsMessage =
    modelSource === "provider" &&
    !providersLoading &&
    Boolean(selectedProvider) &&
    selectedProviderModels.length === 0;
  const showUnavailableCodeAgentModelMessage = unavailableCodeAgentModel;
  const showUnavailableProviderModelMessage = unavailableProviderModel;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setErrorField(null);

    if (!displayName.trim()) {
      const message = "Agent 名称必填。";
      setError(message);
      setErrorField("display_name");
      displayNameRef.current?.focus();
      return;
    }

    if (!systemPrompt.trim()) {
      const message = "系统提示词必填。";
      setError(message);
      setErrorField("system_prompt");
      setSystemPromptView("edit");
      systemPromptRef.current?.focus();
      return;
    }

    if (saveBlocked) return;

    const draft = buildAgentDraftPayload({
      codeAgentModel,
      modelSource,
      selectedProviderId,
      selectedProviderModel,
      systemPrompt,
    });

    if (mode === "create") {
      await onCreate?.({
        description: description.trim() || null,
        display_name: displayName.trim(),
        draft,
      });
      return;
    }

    if (!agent) return;
    await onUpdate?.(agent.id, {
      description: description.trim() || null,
      display_name: displayName.trim(),
      draft,
      enabled,
    });
  }

  const inputClass =
    "h-10 w-full rounded-xl border border-hairline bg-canvas px-3 text-sm text-ink shadow-sm shadow-primary/0 placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 disabled:bg-canvas-soft disabled:text-body";
  const selectClass =
    "h-10 w-full appearance-none rounded-xl border border-hairline bg-canvas bg-[length:1rem_1rem] bg-[right_0.75rem_center] bg-no-repeat pl-3 pr-9 text-sm text-ink shadow-sm shadow-primary/0 placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 disabled:bg-canvas-soft disabled:text-body bg-[url('data:image/svg+xml;utf8,<svg%20xmlns=%22http://www.w3.org/2000/svg%22%20viewBox=%220%200%2020%2020%22%20fill=%22none%22%20stroke=%22%23667085%22%20stroke-width=%221.6%22%20stroke-linecap=%22round%22%20stroke-linejoin=%22round%22><path%20d=%22M6%208l4%204%204-4%22/></svg>')]";
  const textAreaClass =
    "field-sizing-content min-h-[320px] w-full rounded-xl border border-hairline bg-canvas px-3 py-2.5 font-mono text-sm leading-relaxed text-ink shadow-sm shadow-primary/0 placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15";

  return (
    <section className="overflow-hidden rounded-3xl border border-primary/10 bg-canvas/95 shadow-[0_18px_50px_rgba(0,100,224,0.08)]">
      <form
        className="space-y-4 p-4 sm:p-5"
        noValidate
        onSubmit={(event) => {
          void handleSubmit(event);
        }}
      >
        <div className="flex flex-col-reverse gap-3 border-b border-hairline pb-4 sm:flex-row sm:items-center sm:justify-between">
          {mode === "edit" ? (
            <label className="flex items-center gap-2 text-xs text-body">
              <input
                checked={enabled}
                className="h-4 w-4 rounded border-hairline text-primary"
                onChange={(event) => setEnabled(event.target.checked)}
                type="checkbox"
              />
              启用 Agent
            </label>
          ) : (
            <span aria-hidden="true" />
          )}
          <div className="flex justify-end gap-2">
            {onCancel ? (
              <Button onClick={onCancel} type="button" variant="secondary">
                取消
              </Button>
            ) : null}
            <Button
              aria-busy={pending}
              disabled={pending || saveBlocked}
              type="submit"
              variant="primary"
            >
              {pending ? "保存中..." : "保存 Agent"}
            </Button>
          </div>
        </div>

        {error ? (
          <p
            className="rounded-lg bg-error-soft px-3 py-2 text-xs text-error-deep"
            id={errorId}
            role="alert"
          >
            {error}
          </p>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Agent 名称" required>
            <input
              aria-describedby={errorField === "display_name" ? errorId : undefined}
              aria-invalid={errorField === "display_name" || undefined}
              aria-required="true"
              autoComplete="off"
              className={inputClass}
              name="display_name"
              onChange={(event) => setDisplayName(event.target.value)}
              ref={displayNameRef}
              value={displayName}
            />
          </Field>
          <Field label="Description">
            <input
              autoComplete="off"
              className={inputClass}
              name="description"
              onChange={(event) => setDescription(event.target.value)}
              value={description}
            />
          </Field>
        </div>

        <div className="grid gap-3 lg:grid-cols-3">
          <Field label="模型来源">
            <select
              className={selectClass}
              name="model_source"
              onChange={(event) => setModelSource(event.target.value as ModelSource)}
              value={modelSource}
            >
              <option value="codeagent">CodeAgent</option>
              <option value="provider">LLM Provider</option>
            </select>
          </Field>

          {modelSource === "codeagent" ? (
            <Field label="CodeAgent 模型">
              <select
                className={selectClass}
                name="codeagent_model"
                onChange={(event) => setCodeAgentModel(event.target.value)}
                value={codeAgentModel}
              >
                {unavailableCodeAgentModel ? (
                  <option disabled value={codeAgentModel}>
                    {codeAgentModel} (不可用)
                  </option>
                ) : null}
                {CODEAGENT_MODEL_OPTIONS.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
            </Field>
          ) : (
            <>
              <Field label="LLM Provider">
                <select
                  className={selectClass}
                  disabled={providersLoading || enabledProviders.length === 0}
                  name="provider_id"
                  onChange={(event) => {
                    const nextProviderId = event.target.value;
                    const nextProvider = enabledProviders.find(
                      (provider) => provider.id === nextProviderId,
                    );
                    setSelectedProviderId(nextProviderId);
                    setSelectedProviderModel(nextProvider?.models[0] ?? "");
                  }}
                  value={selectedProviderId}
                >
                  {providersLoading ? (
                    <option value="">Provider 加载中...</option>
                  ) : null}
                  {!providersLoading && enabledProviders.length === 0 ? (
                    <option value="">暂无可用 Provider</option>
                  ) : null}
                  {unavailableDraftProvider ? (
                    <option disabled value={selectedProviderId}>
                      {selectedProviderId} (不可用)
                    </option>
                  ) : null}
                  {enabledProviders.map((provider) => (
                    <option key={provider.id} value={provider.id}>
                      {provider.display_name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Provider 模型">
                <select
                  className={selectClass}
                  disabled={selectedProviderModels.length === 0}
                  name="provider_model"
                  onChange={(event) => setSelectedProviderModel(event.target.value)}
                  value={selectedProviderModel}
                >
                  {unavailableProviderModel ? (
                    <option disabled value={selectedProviderModel}>
                      {selectedProviderModel} (不可用)
                    </option>
                  ) : null}
                  {selectedProviderModels.length === 0 ? (
                    <option value={selectedProviderModel}>
                      {selectedProviderModel || "暂无模型"}
                    </option>
                  ) : null}
                  {selectedProviderModels.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              </Field>
            </>
          )}
        </div>

        {showUnavailableProviderMessage ? (
          <p className="rounded-lg bg-error-soft px-3 py-2 text-xs text-error-deep">
            当前 draft 引用的 Provider 不可用，请选择一个已启用的 LLM Provider。
          </p>
        ) : null}

        {showUnavailableProviderModelMessage ? (
          <p className="rounded-lg bg-error-soft px-3 py-2 text-xs text-error-deep">
            当前 draft 引用的模型不在所选 Provider 的模型列表中，请重新选择模型。
          </p>
        ) : null}

        {showUnavailableCodeAgentModelMessage ? (
          <p className="rounded-lg bg-error-soft px-3 py-2 text-xs text-error-deep">
            当前 draft 引用的 CodeAgent 模型不在可选列表中，请重新选择模型。
          </p>
        ) : null}

        {showProviderModelsMessage ? (
          <p className="rounded-lg bg-warning/15 px-3 py-2 text-xs text-charcoal">
            先到 LLM Provider 页面补模型列表
          </p>
        ) : null}

        <div className="space-y-1">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1">
              <label className="text-sm font-medium text-ink" htmlFor={systemPromptId}>
                系统提示词
              </label>
              <span aria-hidden="true" className="text-error-deep">
                *
              </span>
            </div>
            <button
              aria-label={
                systemPromptView === "edit" ? "切换到预览模式" : "切换到编辑模式"
              }
              aria-pressed={systemPromptView === "preview"}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-hairline bg-canvas text-mute transition-colors hover:border-primary/40 hover:text-ink"
              onClick={() =>
                setSystemPromptView((view) => (view === "edit" ? "preview" : "edit"))
              }
              title={systemPromptView === "edit" ? "预览" : "编辑"}
              type="button"
            >
              {systemPromptView === "edit" ? <EyeIcon /> : <PencilIcon />}
            </button>
          </div>
          {systemPromptView === "edit" ? (
            <textarea
              aria-describedby={errorField === "system_prompt" ? errorId : undefined}
              aria-invalid={errorField === "system_prompt" || undefined}
              aria-required="true"
              className={textAreaClass}
              id={systemPromptId}
              name="system_prompt"
              onChange={(event) => setSystemPrompt(event.target.value)}
              ref={systemPromptRef}
              value={systemPrompt}
            />
          ) : (
            <div
              aria-label="系统提示词预览"
              className="min-h-[320px] overflow-auto rounded-xl border border-dashed border-hairline bg-canvas-soft/60 px-3 py-2.5"
            >
              {systemPrompt.trim() ? (
                <StreamMarkdown>{systemPrompt}</StreamMarkdown>
              ) : (
                <p className="text-xs text-mute">尚未填写系统提示词，预览为空。</p>
              )}
            </div>
          )}
        </div>
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
      <div className="flex h-5 items-center gap-1 leading-5">
        <label className="text-sm font-medium text-ink" htmlFor={id}>
          {label}
        </label>
        <span
          aria-hidden="true"
          className={`text-error-deep ${required ? "" : "invisible"}`}
        >
          *
        </span>
      </div>
      <div className="[&>input]:w-full [&>select]:w-full [&>textarea]:w-full">
        {cloneWithId(children, id)}
      </div>
    </div>
  );
}

export function buildAgentDraftPayload({
  codeAgentModel,
  modelSource,
  selectedProviderId,
  selectedProviderModel,
  systemPrompt,
}: {
  codeAgentModel: string;
  modelSource: ModelSource;
  selectedProviderId: string;
  selectedProviderModel: string;
  systemPrompt: string;
}): AgentDraftConfig {
  const selectedModel =
    modelSource === "provider" ? selectedProviderModel : codeAgentModel;

  return {
    mcp_server_ids: [],
    model: selectedModel.trim(),
    model_config: {},
    provider_id: modelSource === "provider" ? selectedProviderId.trim() : null,
    system_prompt: systemPrompt.trim(),
    tool_allowlist: [],
  };
}

function cloneWithId(children: ReactNode, id: string) {
  if (!isValidElement(children)) return children;
  return cloneElement(children as ReactElement<{ id?: string }>, { id });
}

function EyeIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function PencilIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <path d="M16 3l5 5-12 12H4v-5z" />
      <path d="M14 5l5 5" />
    </svg>
  );
}
