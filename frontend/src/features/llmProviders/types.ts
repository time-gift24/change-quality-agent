export const LLM_PROVIDER_TYPES = [
  "openai",
  "anthropic",
  "azure_openai",
  "azure_ai",
  "google_vertexai",
  "google_genai",
  "anthropic_bedrock",
  "bedrock",
  "bedrock_converse",
  "cohere",
  "fireworks",
  "together",
  "mistralai",
  "huggingface",
  "groq",
  "ollama",
  "google_anthropic_vertex",
  "deepseek",
  "ibm",
  "nvidia",
  "xai",
  "openrouter",
  "perplexity",
  "upstage",
  "baseten",
  "litellm",
] as const;

export type LlmProviderType = (typeof LLM_PROVIDER_TYPES)[number];

export type LlmProviderCreate = {
  display_name: string;
  description?: string | null;
  provider_type: LlmProviderType;
  base_url?: string | null;
  api_key?: string | null;
  default_headers?: Record<string, string>;
  default_query?: Record<string, string>;
  models?: string[];
  enabled?: boolean;
};

export type LlmProviderUpdate = {
  display_name?: string | null;
  description?: string | null;
  provider_type?: LlmProviderType | null;
  base_url?: string | null;
  api_key?: string | null;
  default_headers?: Record<string, string> | null;
  default_query?: Record<string, string> | null;
  models?: string[] | null;
  enabled?: boolean | null;
};

export type LlmProviderSummary = {
  id: string;
  display_name: string;
  description: string | null;
  provider_type: string;
  base_url: string | null;
  default_headers: Record<string, string>;
  default_query: Record<string, string>;
  models: string[];
  enabled: boolean;
  created_at: string;
  updated_at: string;
  api_key_configured: boolean;
};

export type LlmProviderDetail = LlmProviderSummary;

export type LlmProviderModelTestResponse = {
  status: "ok" | "failed";
  latency_ms: number;
  message: string | null;
  error: string | null;
  request: Record<string, unknown> | null;
  response: Record<string, unknown> | null;
};
