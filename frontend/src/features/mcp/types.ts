export type McpTransport = "stdio" | "http";

export type McpDesiredState = "running" | "stopped";

export type McpServerRuntimeStatus =
  | "unknown"
  | "starting"
  | "running"
  | "stopping"
  | "stopped"
  | "error";

export type McpServerTool = {
  name: string;
  description: string | null;
  input_schema: Record<string, unknown>;
  discovered_at: string | null;
};

export type McpServerCreate = {
  name: string;
  transport: McpTransport;
  command?: string | null;
  args?: string[];
  env?: Record<string, string>;
  url?: string | null;
  headers?: Record<string, string>;
  enabled?: boolean;
  desired_state?: McpDesiredState;
};

export type McpServerUpdate = {
  name?: string | null;
  command?: string | null;
  args?: string[];
  env?: Record<string, string>;
  url?: string | null;
  headers?: Record<string, string>;
  enabled?: boolean;
  desired_state?: McpDesiredState;
};

export type McpServerSummary = {
  id: string;
  name: string;
  transport: McpTransport;
  command: string | null;
  args: string[];
  env: Record<string, string>;
  url: string | null;
  headers: Record<string, string>;
  enabled: boolean;
  desired_state: McpDesiredState;
  runtime_status: McpServerRuntimeStatus;
  last_checked_at: string | null;
  last_error: string | null;
  tool_count: number;
};

export type McpServerDetail = McpServerSummary & {
  tools: McpServerTool[];
};

export type McpLifecycleResponse = {
  server_id: string;
  desired_state: McpDesiredState;
  runtime_status: McpServerRuntimeStatus;
  last_checked_at: string | null;
  last_error: string | null;
  tool_count: number;
};
