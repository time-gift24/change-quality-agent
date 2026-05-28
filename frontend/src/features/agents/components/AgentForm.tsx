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
  const [systemPrompt, setSystemPrompt] = useState("");
  const [modelSource, setModelSource] = useState<ModelSource>("codeagent");
  const [codeAgentModel, setCodeAgentModel] = useState<string>(
    DEFAULT_CODEAGENT_MODEL,
  );
  const [selectedProviderId, setSelectedProviderId] = useState("");
  const [selectedProviderModel, setSelectedProviderModel] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const displayNameRef = useRef<HTMLInputElement>(null);
  const systemPromptRef = useRef<HTMLTextAreaElement>(null);
  const errorId = useId();

  useEffect(() => {
    setError(null);

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
    setSystemPrompt("");
    setEnabled(true);
    setModelSource("codeagent");
    setCodeAgentModel(DEFAULT_CODEAGENT_MODEL);
    setSelectedProviderId("");
    setSelectedProviderModel("");
  }, [agent, mode]);

  useEffect(() => {
    if (mode !== "create") return;
    if (modelSource !== "provider" || enabledProviders.length === 0) return;
    if (enabledProviders.some((provider) => provider.id === selectedProviderId)) return;
    setSelectedProviderId(enabledProviders[0]?.id ?? "");
  }, [enabledProviders, mode, modelSource, selectedProviderId]);

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
    if (mode !== "create") return;
    if (modelSource !== "provider" || !selectedProvider) return;
    if (selectedProvider.models.length === 0) {
      if (selectedProviderModel) setSelectedProviderModel("");
      return;
    }
    if (!selectedProvider.models.includes(selectedProviderModel)) {
      setSelectedProviderModel(selectedProvider.models[0] ?? "");
    }
  }, [mode, modelSource, selectedProvider, selectedProviderModel]);

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

    if (!displayName.trim()) {
      const message = "Agent 名称必填。";
      setError(message);
      displayNameRef.current?.focus();
      return;
    }

    if (!systemPrompt.trim()) {
      const message = "System Prompt 必填。";
      setError(message);
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
  const textAreaClass =
    "min-h-[96px] w-full resize-y rounded-xl border border-hairline bg-canvas px-3 py-2.5 font-mono text-sm leading-relaxed text-ink shadow-sm shadow-primary/0 placeholder:text-mute outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15";

  return (
    <section className="overflow-hidden rounded-3xl border border-primary/10 bg-canvas/95 shadow-[0_18px_50px_rgba(0,100,224,0.08)]">
      <form
        className="space-y-4 p-4 sm:p-5"
        noValidate
        onSubmit={(event) => {
          void handleSubmit(event);
        }}
      >
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
          <Field label="Agent 名称">
            <input
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

        <Field label="System Prompt">
          <textarea
            className={textAreaClass}
            name="system_prompt"
            onChange={(event) => setSystemPrompt(event.target.value)}
            ref={systemPromptRef}
            value={systemPrompt}
          />
        </Field>

        <div className="grid gap-3 lg:grid-cols-3">
          <Field label="模型来源">
            <select
              className={inputClass}
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
                className={inputClass}
                name="codeagent_model"
                onChange={(event) => setCodeAgentModel(event.target.value)}
                value={codeAgentModel}
              >
                {unavailableCodeAgentModel ? (
                  <option value={codeAgentModel}>
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
                  className={inputClass}
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
                    <option value={selectedProviderId}>
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
                  className={inputClass}
                  disabled={selectedProviderModels.length === 0}
                  name="provider_model"
                  onChange={(event) => setSelectedProviderModel(event.target.value)}
                  value={selectedProviderModel}
                >
                  {unavailableProviderModel ? (
                    <option value={selectedProviderModel}>
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
        ) : null}

        <div className="flex justify-end gap-2 border-t border-hairline pt-4">
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
      </form>
    </section>
  );
}

function Field({
  children,
  label,
}: {
  children: ReactNode;
  label: string;
}) {
  const id = useId();
  return (
    <div className="space-y-1">
      <label className="text-sm font-medium text-ink" htmlFor={id}>
        {label}
      </label>
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
