import type { RunStatus } from "../runs/types";

export type SopEnvironment = {
  key: string;
  name_en: string;
  name_zh: string;
};

export type SopPreview = {
  sop_id?: string;
  env_key?: string;
  raw_payload?: unknown;
  [key: string]: unknown;
};

export type SopRunHistoryItem = {
  run_id: string;
  status?: RunStatus | string | null;
  created_at?: string | null;
};

export type StartSopRunResult =
  | {
      kind: "started";
      runId: string;
    }
  | {
      kind: "active";
      runId: string;
    };
