export type LlmProviderCreate = {
  key: string;
  display_name: string;
  description?: string | null;
  provider_type: string;
  base_url?: string | null;
  api_key?: string | null;
  default_headers?: Record<string, string>;
  default_query?: Record<string, string>;
  enabled?: boolean;
};

export type LlmProviderUpdate = {
  display_name?: string | null;
  description?: string | null;
  provider_type?: string | null;
  base_url?: string | null;
  api_key?: string | null;
  default_headers?: Record<string, string> | null;
  default_query?: Record<string, string> | null;
  enabled?: boolean | null;
};

export type LlmProviderSummary = {
  id: string;
  key: string;
  display_name: string;
  description: string | null;
  provider_type: string;
  base_url: string | null;
  default_headers: Record<string, string>;
  default_query: Record<string, string>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  api_key_configured: boolean;
};

export type LlmProviderDetail = LlmProviderSummary;
