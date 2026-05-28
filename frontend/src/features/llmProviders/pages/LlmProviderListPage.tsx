import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { LlmProviderTable } from "../components/LlmProviderTable";
import { useLlmProviders } from "../hooks";
import { LlmProviderPageLayout } from "./LlmProviderPageLayout";

export function LlmProviderListPage() {
  const providersState = useLlmProviders();
  const [searchText, setSearchText] = useState("");
  const navigate = useNavigate();

  const filteredProviders = useMemo(() => {
    const query = searchText.trim().toLowerCase();
    if (!query) return providersState.data;
    return providersState.data.filter((provider) => {
      return (
        provider.id.toLowerCase().includes(query) ||
        provider.display_name.toLowerCase().includes(query) ||
        provider.provider_type.toLowerCase().includes(query)
      );
    });
  }, [providersState.data, searchText]);

  return (
    <LlmProviderPageLayout
      description="管理普通 LangChain provider；CodeAgent 仍走内部专用 factory。"
      items={[{ label: "LLM Providers" }]}
      title="LLM Providers"
    >
      <LlmProviderTable
        error={providersState.error}
        loading={providersState.loading}
        onCreateProvider={() => navigate("/llm-providers/new")}
        onRefresh={() => { void providersState.refetch(); }}
        onSearchTextChange={setSearchText}
        providers={filteredProviders}
        searchText={searchText}
      />
    </LlmProviderPageLayout>
  );
}
