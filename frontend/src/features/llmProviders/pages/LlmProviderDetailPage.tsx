import { useLocation, useNavigate, useParams } from "react-router-dom";
import { useState } from "react";

import { Button } from "../../../components/ui/button";
import { StreamMarkdown } from "../../sop-quality-checks/components/StreamMarkdown";
import { LlmProviderForm } from "../components/LlmProviderForm";
import { useLlmProviderDetail, useLlmProviderMutations } from "../hooks";
import type { LlmProviderDetail, LlmProviderModelTestResponse } from "../types";
import { LlmProviderPageLayout } from "./LlmProviderPageLayout";

export function LlmProviderDetailPage() {
  const { providerId } = useParams<{ providerId: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const detailState = useLlmProviderDetail(providerId ?? null);
  const mutations = useLlmProviderMutations();
  const provider = detailState.data;
  const targetId = provider?.id ?? providerId ?? "";
  const notice = getNavigationNotice(location.state);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  async function handleDelete() {
    if (!provider) return;
    await mutations.deleteProvider(targetId);
    navigate("/llm-providers", { replace: true });
  }

  return (
    <LlmProviderPageLayout
      actions={provider ? (
        <>
          <Button onClick={() => navigate(`/llm-providers/${targetId}/edit`)} variant="secondary">
            编辑
          </Button>
          <Button disabled={mutations.pending} onClick={() => setConfirmingDelete(true)} variant="destructive">
            {mutations.pending ? "删除中…" : "删除"}
          </Button>
        </>
      ) : null}
      description={provider ? `${provider.provider_type} · ${provider.enabled ? "enabled" : "disabled"}` : "查看 provider 配置。"}
      items={[
        { label: "LLM Providers", to: "/llm-providers" },
        { label: provider?.display_name ?? providerId ?? "...", to: `/llm-providers/${targetId}` },
        { label: "查看" },
      ]}
      title={provider?.display_name ?? providerId ?? "LLM Provider"}
    >
      {notice ? <SuccessNotice message={notice} /> : null}
      {mutations.error ? <ErrorAlert message={mutations.error.message} /> : null}
      {detailState.loading && !provider ? <p className="text-xs text-mute">加载详情中…</p> : null}
      {detailState.error && !detailState.loading ? <ErrorAlert message={detailState.error.message} /> : null}
      {provider && confirmingDelete ? (
        <DeleteConfirm
          displayName={provider.display_name}
          onCancel={() => setConfirmingDelete(false)}
          onConfirm={() => { void handleDelete(); }}
          pending={mutations.pending}
        />
      ) : null}
      {provider ? (
        <DetailContent
          provider={provider}
          testProviderModel={mutations.testProviderModel}
        />
      ) : null}
    </LlmProviderPageLayout>
  );
}

function DetailContent({
  provider,
  testProviderModel,
}: {
  provider: LlmProviderDetail;
  testProviderModel: (providerId: string, model: string) => Promise<LlmProviderModelTestResponse>;
}) {
  const [testResults, setTestResults] = useState<
    Record<string, LlmProviderModelTestResponse>
  >({});
  const [pendingModel, setPendingModel] = useState<string | null>(null);

  async function handleTest(model: string) {
    setPendingModel(model);
    try {
      const result = await testProviderModel(provider.id, model);
      setTestResults((current) => ({ ...current, [model]: result }));
    } catch (error) {
      setTestResults((current) => ({
        ...current,
        [model]: {
          error: error instanceof Error ? error.message : String(error),
          latency_ms: 0,
          message: null,
          request: null,
          response: null,
          status: "failed",
        },
      }));
    } finally {
      setPendingModel(null);
    }
  }

  return (
    <div className="grid max-w-7xl gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-w-0 space-y-4">
        <LlmProviderForm mode="view" provider={provider} />
        <ModelsPanel
          models={provider.models}
          onTest={(model) => { void handleTest(model); }}
          pendingModel={pendingModel}
          results={testResults}
        />
        <ConfigMapPanel title="Default Headers" values={provider.default_headers} />
        <ConfigMapPanel title="Default Query" values={provider.default_query} />
      </div>
      <aside aria-label="配置总览" className="space-y-3 xl:sticky xl:top-4 xl:self-start">
        <div className="overflow-hidden rounded-3xl border border-primary/10 bg-canvas/90 shadow-[0_18px_45px_rgba(0,100,224,0.07)]">
          <div className="border-b border-primary/10 bg-primary-soft/60 px-4 py-3">
            <p className="font-mono text-2xs uppercase tracking-[0.18em] text-primary-deep">
              Provider Overview
            </p>
            <h2 className="mt-1 text-sm font-semibold text-ink">配置总览</h2>
            <p className="mt-1 truncate text-xs text-body">{provider.id}</p>
          </div>
          <dl className="space-y-3 p-4 text-xs">
            <InfoRow label="Provider Type" value={provider.provider_type} />
            <InfoRow label="Base URL" value={provider.base_url ?? "-"} />
            <InfoRow label="API Key" value={provider.api_key_configured ? "configured" : "missing"} />
            <InfoRow label="Models" value={String(provider.models.length)} />
            <InfoRow label="状态" value={provider.enabled ? "enabled" : "disabled"} />
          </dl>
        </div>
      </aside>
    </div>
  );
}

function ModelsPanel({
  models,
  onTest,
  pendingModel,
  results,
}: {
  models: string[];
  onTest: (model: string) => void;
  pendingModel: string | null;
  results: Record<string, LlmProviderModelTestResponse>;
}) {
  return (
    <section className="rounded-3xl border border-hairline-soft bg-canvas p-4">
      <h2 className="text-sm font-semibold text-ink">Models</h2>
      {models.length === 0 ? (
        <p className="mt-2 text-xs text-mute">未配置模型，无法测试连通性。</p>
      ) : (
        <div className="mt-3 space-y-2">
          {models.map((model) => (
            <div
              className="rounded-2xl border border-hairline bg-canvas-soft/40 p-3"
              key={model}
            >
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <code className="break-all text-xs text-ink">{model}</code>
                <Button
                  aria-busy={pendingModel === model}
                  disabled={pendingModel === model}
                  onClick={() => onTest(model)}
                  type="button"
                  variant="secondary"
                >
                  {pendingModel === model ? `测试中 ${model}` : `测试 ${model}`}
                </Button>
              </div>
              {pendingModel === model ? (
                <p aria-busy="true" className="mt-2 text-xs text-mute" role="status">
                  正在测试连通性…
                </p>
              ) : null}
              {results[model] ? <ModelTestResult result={results[model]} /> : null}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function ModelTestResult({ result }: { result: LlmProviderModelTestResponse }) {
  if (result.status === "ok") {
    return (
      <>
        <p className="mt-2 text-xs text-success" role="status">
          连通成功 · {result.latency_ms}ms
        </p>
        <InteractionTrace result={result} />
      </>
    );
  }

  return (
    <>
      <p className="mt-2 text-xs text-error-deep" role="alert">
        连通失败 · {result.latency_ms}ms · {result.error ?? "unknown error"}
      </p>
      <InteractionTrace result={result} />
    </>
  );
}

function InteractionTrace({ result }: { result: LlmProviderModelTestResponse }) {
  const content = responseContent(result);
  return (
    <div className="mt-3 space-y-3">
      {content ? (
        <section className="rounded-2xl border border-hairline bg-canvas p-3">
          <h3 className="text-xs font-semibold text-ink">模型响应</h3>
          <div className="mt-2 text-sm text-ink">
            <StreamMarkdown>{content}</StreamMarkdown>
          </div>
        </section>
      ) : null}
      <details className="rounded-2xl border border-hairline bg-canvas p-3">
        <summary className="cursor-pointer text-xs font-semibold text-ink">
          完整交互信息
        </summary>
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          <TraceBlock title="Request" value={result.request} />
          <TraceBlock title="Response" value={result.response} />
        </div>
      </details>
    </div>
  );
}

function TraceBlock({
  title,
  value,
}: {
  title: string;
  value: Record<string, unknown> | null;
}) {
  return (
    <section>
      <h4 className="text-xs font-semibold text-mute">{title}</h4>
      <pre className="mt-1 max-h-96 overflow-auto rounded-xl bg-ink-deep p-3 text-xs leading-relaxed text-on-ink-button">
        {JSON.stringify(value ?? {}, null, 2)}
      </pre>
    </section>
  );
}

function responseContent(result: LlmProviderModelTestResponse): string {
  const responseContentValue = result.response?.content;
  if (typeof responseContentValue === "string" && responseContentValue.trim()) {
    return responseContentValue;
  }
  return result.message ?? "";
}

function ConfigMapPanel({
  title,
  values,
}: {
  title: string;
  values: Record<string, string>;
}) {
  return (
    <section className="rounded-3xl border border-hairline-soft bg-canvas p-4">
      <h2 className="text-sm font-semibold text-ink">{title}</h2>
      {Object.keys(values).length === 0 ? (
        <p className="mt-2 text-xs text-mute">未配置</p>
      ) : (
        <dl className="mt-3 space-y-2">
          {Object.entries(values).map(([key, value]) => (
            <InfoRow key={key} label={key} value={value} />
          ))}
        </dl>
      )}
    </section>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="text-mute">{label}</dt>
      <dd className="min-w-0 break-all text-right font-mono text-xs text-ink">{value}</dd>
    </div>
  );
}

function DeleteConfirm({
  displayName,
  onCancel,
  onConfirm,
  pending,
}: {
  displayName: string;
  onCancel: () => void;
  onConfirm: () => void;
  pending: boolean;
}) {
  return (
    <section
      aria-labelledby="delete-provider-title"
      className="mb-3 rounded-2xl border border-error/30 bg-error-soft/40 p-3"
      role="alertdialog"
    >
      <h2 className="text-sm font-semibold text-error-deep" id="delete-provider-title">
        确认删除 Provider？
      </h2>
      <p className="mt-1 text-sm text-body">
        将删除 {displayName}。删除后 Agent version 无法再通过这个 provider 发起新运行。
      </p>
      <div className="mt-3 flex justify-end gap-2">
        <Button disabled={pending} onClick={onCancel} variant="secondary">
          取消
        </Button>
        <Button aria-busy={pending} disabled={pending} onClick={onConfirm} variant="destructive">
          {pending ? "删除中…" : "确认删除"}
        </Button>
      </div>
    </section>
  );
}

function SuccessNotice({ message }: { message: string }) {
  return (
    <p className="mb-3 rounded-xl border border-success/20 bg-success/10 px-3 py-2 text-xs text-success" role="status">
      {message}
    </p>
  );
}

function ErrorAlert({ message }: { message: string }) {
  return (
    <p className="mb-3 rounded-xl border border-error-soft bg-canvas px-3 py-2 text-xs text-error-deep" role="alert">
      {message}
    </p>
  );
}

function getNavigationNotice(state: unknown): string | null {
  if (!state || typeof state !== "object") return null;
  const maybeNotice = (state as { llmProviderNotice?: unknown }).llmProviderNotice;
  return typeof maybeNotice === "string" && maybeNotice.trim() ? maybeNotice : null;
}
