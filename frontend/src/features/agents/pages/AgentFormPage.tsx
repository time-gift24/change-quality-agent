import { useNavigate, useParams } from "react-router-dom";

import { AgentForm } from "../components/AgentForm";
import { useAgentDetail, useAgentMutations } from "../hooks";
import { useLlmProviders } from "../../llmProviders/hooks";
import { AgentPageLayout } from "./AgentPageLayout";

export function AgentCreatePage() {
  const navigate = useNavigate();
  const mutations = useAgentMutations();
  const providersState = useLlmProviders();

  return (
    <AgentPageLayout
      description="创建 ReAct Agent 配置草稿，选择模型来源并填写系统提示词。"
      items={[{ label: "Agent 配置", to: "/agents" }, { label: "新增" }]}
      title="新增 Agent"
    >
      {mutations.error ? (
        <p
          className="rounded-lg bg-error-soft px-3 py-2 text-xs text-error-deep"
          role="alert"
        >
          {mutations.error.message}
        </p>
      ) : null}
      <AgentForm
        agent={null}
        mode="create"
        onCancel={() => navigate("/agents")}
        onCreate={async (payload) => {
          await mutations.createAgent(payload);
          navigate("/agents", { state: { agentNotice: "Agent 已创建。" } });
        }}
        pending={mutations.pending}
        providers={providersState.data}
        providersLoading={providersState.loading}
      />
    </AgentPageLayout>
  );
}

export function AgentEditPage() {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();
  const detailState = useAgentDetail(agentId ?? null);
  const providersState = useLlmProviders();
  const mutations = useAgentMutations();
  const agent = detailState.data;

  return (
    <AgentPageLayout
      description={agent ? `${agent.draft?.model ?? "..."} · ${agent.enabled ? "已启用" : "已停用"}` : "修改 Agent 配置草稿。"}
      items={[
        { label: "Agent 配置", to: "/agents" },
        { label: agent?.display_name ?? agentId ?? "..." },
        { label: "编辑" },
      ]}
      title="编辑 Agent"
    >
      {detailState.loading && !agent ? (
        <p className="text-xs text-mute">加载编辑表单中…</p>
      ) : null}
      {detailState.error && !detailState.loading ? (
        <p
          className="rounded-lg bg-error-soft px-3 py-2 text-xs text-error-deep"
          role="alert"
        >
          {detailState.error.message}
        </p>
      ) : null}
      {agent ? (
        <>
          {mutations.error ? (
            <p
              className="rounded-lg bg-error-soft px-3 py-2 text-xs text-error-deep"
              role="alert"
            >
              {mutations.error.message}
            </p>
          ) : null}
          <AgentForm
            agent={agent}
            mode="edit"
            onCancel={() => navigate("/agents")}
            onUpdate={async (id, payload) => {
              await mutations.updateAgentDraft(id, payload);
              navigate("/agents", { state: { agentNotice: "Agent 已保存。" } });
            }}
            pending={mutations.pending}
            providers={providersState.data}
            providersLoading={providersState.loading}
          />
        </>
      ) : null}
    </AgentPageLayout>
  );
}
