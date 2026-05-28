import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { AgentTable } from "../components/AgentTable";
import { useLlmProviders } from "../../llmProviders/hooks";
import { useAgents } from "../hooks";
import { AgentPageLayout } from "./AgentPageLayout";

export function AgentListPage() {
  const agentsState = useAgents();
  const providersState = useLlmProviders();
  const [searchText, setSearchText] = useState("");
  const navigate = useNavigate();

  const filteredAgents = useMemo(() => {
    const query = searchText.trim().toLowerCase();
    if (!query) return agentsState.data;

    return agentsState.data.filter((agent) => {
      const latestModel = agent.latest_version?.model ?? "";
      return (
        agent.id.toLowerCase().includes(query) ||
        agent.display_name.toLowerCase().includes(query) ||
        (agent.description ?? "").toLowerCase().includes(query) ||
        latestModel.toLowerCase().includes(query)
      );
    });
  }, [agentsState.data, searchText]);

  return (
    <AgentPageLayout
      description="管理 ReAct Agent 的启停状态、发布模型和待发布草稿。"
      items={[{ label: "Agent 配置" }]}
      title="Agent 配置"
    >
      <AgentTable
        agents={filteredAgents}
        error={agentsState.error ?? providersState.error}
        loading={agentsState.loading || providersState.loading}
        onCreateAgent={() => navigate("/agents/new")}
        onRefresh={() => {
          void agentsState.refetch();
          void providersState.refetch();
        }}
        onSearchTextChange={setSearchText}
        providers={providersState.data}
        searchText={searchText}
      />
    </AgentPageLayout>
  );
}
