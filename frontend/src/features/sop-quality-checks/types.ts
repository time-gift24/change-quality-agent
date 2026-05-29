export type SopQualityCheckStatus =
  | "pending"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "interrupted";

export type SopQualityNodeState = {
  status: "idle" | "running" | "done" | "error" | "interrupted";
  streamText: string;
  thinkingText?: string;
  error?: string;
  firstSequence?: number;
};

export type SopQualityDisplayState = {
  latest_sequence: number;
  nodes: Record<string, SopQualityNodeState>;
  is_running: boolean;
};

export type SopQualityCheckDetail = {
  check_id: string;
  sop_id: string;
  env_key: string;
  status: SopQualityCheckStatus;
  quality_result?: string | null;
  latest_sequence: number;
  current_checkpoint_id?: string | null;
  result?: Record<string, unknown> | null;
  error?: Record<string, unknown> | null;
  display_state: SopQualityDisplayState;
  session_id?: number | null;
};

export type SopQualityCheckEvent = {
  check_id: string;
  sequence: number;
  type:
    | "created"
    | "started"
    | "messages"
    | "updates"
    | "checkpoint"
    | "completed"
    | "failed"
    | "interrupted";
  node?: string | null;
  channel?: "thinking" | "summary" | "result" | null;
  checkpoint_id?: string | null;
  task_id?: string | null;
  message?: string | null;
  created_at?: string | null;
};

export type StartSopQualityCheckResult =
  | { kind: "created"; checkId: string }
  | { kind: "active"; checkId: string };
