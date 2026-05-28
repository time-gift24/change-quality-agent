import type { ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { LlmProviderForm } from "../components/LlmProviderForm";
import { useLlmProviderDetail, useLlmProviderMutations } from "../hooks";
import type { LlmProviderDetail } from "../types";
import { LlmProviderPageLayout } from "./LlmProviderPageLayout";

export function LlmProviderCreatePage() {
  const navigate = useNavigate();
  const mutations = useLlmProviderMutations();

  return (
    <LlmProviderPageLayout
      description="保存普通 LangChain provider，Agent version 可通过 provider_id 引用。"
      items={[{ label: "LLM Providers", to: "/llm-providers" }, { label: "新增" }]}
      title="新增 LLM Provider"
    >
      <FormGrid aside={<ProviderNote title="保存策略" lines={["API Key 只写不读，保存后只显示是否已配置。", "Headers 和 Query 使用 KEY=VALUE，每行一条。", "CodeAgent 不在这里配置，继续使用 codeagent:<model>。"]} />}>
        {mutations.error ? <ErrorAlert message={mutations.error.message} /> : null}
        <LlmProviderForm
          mode="create"
          onCancel={() => navigate("/llm-providers")}
          onCreate={async (payload) => {
            const created = await mutations.createProvider(payload);
            navigate(`/llm-providers/${created.id}`, {
              state: { llmProviderNotice: "LLM Provider 已创建。" },
            });
          }}
          pending={mutations.pending}
          provider={null}
        />
      </FormGrid>
    </LlmProviderPageLayout>
  );
}

export function LlmProviderEditPage() {
  const { providerId } = useParams<{ providerId: string }>();
  const navigate = useNavigate();
  const detailState = useLlmProviderDetail(providerId ?? null);
  const mutations = useLlmProviderMutations();
  const provider = detailState.data;
  const targetId = provider?.id ?? providerId ?? "";

  return (
    <LlmProviderPageLayout
      description={provider ? `${provider.provider_type} · ${provider.enabled ? "enabled" : "disabled"}` : "修改 provider 配置。"}
      items={[
        { label: "LLM Providers", to: "/llm-providers" },
        { label: provider?.display_name ?? providerId ?? "...", to: `/llm-providers/${targetId}` },
        { label: "编辑" },
      ]}
      title="编辑 LLM Provider"
    >
      {detailState.loading && !provider ? <p className="text-xs text-mute">加载编辑表单中…</p> : null}
      {detailState.error && !detailState.loading ? <ErrorAlert message={detailState.error.message} /> : null}
      {provider ? (
        <FormGrid aside={<ProviderSummary provider={provider} />}>
          {mutations.error ? <ErrorAlert message={mutations.error.message} /> : null}
          <LlmProviderForm
            mode="edit"
            onCancel={() => navigate(`/llm-providers/${targetId}`)}
            onUpdate={async (id, payload) => {
              await mutations.updateProvider(id, payload);
              await detailState.refetch();
              navigate(`/llm-providers/${targetId}`, {
                state: { llmProviderNotice: "LLM Provider 已保存。" },
              });
            }}
            pending={mutations.pending}
            provider={provider}
          />
        </FormGrid>
      ) : null}
    </LlmProviderPageLayout>
  );
}

function FormGrid({ children, aside }: { children: ReactNode; aside: ReactNode }) {
  return (
    <div className="grid max-w-7xl gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-w-0 space-y-4">{children}</div>
      <aside aria-label="配置摘要" className="space-y-3 xl:sticky xl:top-4 xl:self-start">
        {aside}
      </aside>
    </div>
  );
}

function ProviderNote({ title, lines }: { title: string; lines: string[] }) {
  return (
    <div className="overflow-hidden rounded-3xl border border-primary/10 bg-canvas/90 shadow-[0_18px_45px_rgba(0,100,224,0.07)]">
      <div className="border-b border-primary/10 bg-primary-soft/60 px-4 py-3">
        <p className="font-mono text-2xs uppercase tracking-[0.18em] text-primary-deep">
          Provider Policy
        </p>
        <h2 className="mt-1 text-sm font-semibold text-ink">配置摘要</h2>
        <p className="mt-1 text-xs leading-relaxed text-body">{title}</p>
      </div>
      <ol className="space-y-3 p-4">
        {lines.map((line, index) => (
          <li className="flex gap-3" key={line}>
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-2xs font-semibold text-on-primary">
              {index + 1}
            </span>
            <p className="pt-0.5 text-xs leading-relaxed text-body">{line}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}

function ProviderSummary({ provider }: { provider: LlmProviderDetail }) {
  return (
    <ProviderNote
      title={provider.display_name}
      lines={[
        `id: ${provider.id}`,
        `provider_type: ${provider.provider_type}`,
        `api_key: ${provider.api_key_configured ? "configured" : "missing"}`,
      ]}
    />
  );
}

function ErrorAlert({ message }: { message: string }) {
  return (
    <p className="rounded-xl border border-error-soft bg-canvas px-3 py-2 text-xs text-error-deep" role="alert">
      {message}
    </p>
  );
}
