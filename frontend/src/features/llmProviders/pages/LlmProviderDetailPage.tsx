import { useLocation, useNavigate, useParams } from "react-router-dom";

import { Button } from "../../../components/ui/button";
import { LlmProviderForm } from "../components/LlmProviderForm";
import { useLlmProviderDetail, useLlmProviderMutations } from "../hooks";
import type { LlmProviderDetail } from "../types";
import { LlmProviderPageLayout } from "./LlmProviderPageLayout";

export function LlmProviderDetailPage() {
  const { providerKey } = useParams<{ providerKey: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const detailState = useLlmProviderDetail(providerKey ?? null);
  const mutations = useLlmProviderMutations();
  const provider = detailState.data;
  const targetKey = provider?.key ?? providerKey ?? "";
  const notice = getNavigationNotice(location.state);

  async function handleDelete() {
    if (!provider) return;
    if (!window.confirm(`确认删除 ${provider.display_name}？`)) return;
    await mutations.deleteProvider(targetKey);
    navigate("/llm-providers", { replace: true });
  }

  return (
    <LlmProviderPageLayout
      actions={provider ? (
        <>
          <Button onClick={() => navigate(`/llm-providers/${targetKey}/edit`)} variant="secondary">
            编辑
          </Button>
          <Button disabled={mutations.pending} onClick={() => { void handleDelete(); }} variant="destructive">
            删除
          </Button>
        </>
      ) : null}
      description={provider ? `${provider.provider_type} · ${provider.enabled ? "enabled" : "disabled"}` : "查看 provider 配置。"}
      items={[
        { label: "LLM Providers", to: "/llm-providers" },
        { label: provider?.display_name ?? providerKey ?? "...", to: `/llm-providers/${targetKey}` },
        { label: "查看" },
      ]}
      title={provider?.display_name ?? providerKey ?? "LLM Provider"}
    >
      {notice ? <SuccessNotice message={notice} /> : null}
      {mutations.error ? <ErrorAlert message={mutations.error.message} /> : null}
      {detailState.loading && !provider ? <p className="text-xs text-mute">加载详情中…</p> : null}
      {detailState.error && !detailState.loading ? <ErrorAlert message={detailState.error.message} /> : null}
      {provider ? <DetailContent provider={provider} /> : null}
    </LlmProviderPageLayout>
  );
}

function DetailContent({ provider }: { provider: LlmProviderDetail }) {
  return (
    <div className="grid max-w-7xl gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-w-0 space-y-4">
        <LlmProviderForm mode="view" provider={provider} />
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
            <p className="mt-1 truncate text-xs text-body">{provider.key}</p>
          </div>
          <dl className="space-y-3 p-4 text-xs">
            <InfoRow label="Provider Type" value={provider.provider_type} />
            <InfoRow label="Base URL" value={provider.base_url ?? "-"} />
            <InfoRow label="API Key" value={provider.api_key_configured ? "configured" : "missing"} />
            <InfoRow label="状态" value={provider.enabled ? "enabled" : "disabled"} />
          </dl>
        </div>
      </aside>
    </div>
  );
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
      <dd className="min-w-0 break-all text-right font-mono text-2xs text-ink">{value}</dd>
    </div>
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
