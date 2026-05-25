export type RunStatus =
  | "pending"
  | "running"
  | "success"
  | "error"
  | "timeout"
  | "interrupted";

export type RunSummary = {
  run_id: string;
  subject_type: string;
  subject_id: string;
  status: RunStatus;
  current_node: string | null;
  completed_nodes: string[];
  latest_sequence: number;
  started_at?: string | null;
  finished_at?: string | null;
  result_status?: string | null;
  error_summary?: string | null;
};

export type RunEvent = {
  type:
    | "tasks"
    | "messages"
    | "updates"
    | "custom"
    | "checkpoints"
    | "error"
    | "done";
  node: string | null;
  thread_id: string;
  run_id: string;
  checkpoint_id?: string | null;
  sequence: number;
  payload: Record<string, unknown>;
};
