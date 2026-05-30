export const CODEAGENT_MODEL_OPTIONS = [
  "codeagent:deepseek-v4-pro",
  "codeagent:codeagent-v4-pro",
] as const;

export type AgentDraftConfig = {
  system_prompt: string;
  model: string;
  provider_id: string | null;
  model_config: Record<string, unknown>;
  tool_allowlist: string[];
  mcp_server_ids: string[];
};

export type AgentVersionSummary = {
  id: string;
  version_number: number;
  model: string;
  provider_id: string | null;
  published_at: string;
};

export type AgentSummary = {
  id: string;
  display_name: string;
  description: string | null;
  enabled: boolean;
  has_draft: boolean;
  latest_version: AgentVersionSummary | null;
  created_at: string;
  updated_at: string;
};

export type AgentDetail = AgentSummary & {
  draft: AgentDraftConfig | null;
};

export type AgentCreate = {
  display_name: string;
  description?: string | null;
  draft: AgentDraftConfig;
};

export type AgentDraftUpdate = {
  display_name?: string | null;
  description?: string | null;
  enabled?: boolean | null;
  draft?: AgentDraftConfig | null;
};

export type BuiltinAgentToolCapability = {
  name: string;
  label: string;
  description: string | null;
  enabled: boolean;
};

export type McpAgentCapability = {
  id: string;
  name: string;
  enabled: boolean;
  runtime_status: string;
  tool_count: number;
};

export type AgentCapabilities = {
  builtin_tools: BuiltinAgentToolCapability[];
  mcp_servers: McpAgentCapability[];
};

export type AgentSessionStart = {
  message: string;
  session_id?: number | null;
};

export type AgentSessionStartResponse = {
  session_id: number;
  stream_url: string;
};
