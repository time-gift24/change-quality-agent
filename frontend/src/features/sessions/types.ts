export type SessionStatus = "active" | "completed" | "failed" | "interrupted";

export type SessionMessageRole = "user" | "assistant" | "tool" | "system";

export type SessionDetail = {
  id: number;
  thread_id: string;
  status: SessionStatus;
  title: string | null;
  latest_sequence: number;
  created_at: string;
  updated_at: string;
};

export type SessionMessage = {
  id: string;
  session_id: number;
  sequence: number;
  role: SessionMessageRole;
  content: string;
  additional_kwargs: Record<string, unknown>;
  created_at: string;
};

export type SessionStreamEvent =
  | {
      type: "message";
      session_id: number;
      sequence: number;
      role: SessionMessageRole;
      content: string;
      additional_kwargs: Record<string, unknown>;
      created_at?: string | null;
    }
  | {
      type: "message_delta";
      session_id: number;
      sequence: number | null;
      role: SessionMessageRole;
      content: string;
      additional_kwargs: Record<string, unknown>;
    };
