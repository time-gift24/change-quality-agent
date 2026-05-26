import type { RunStatus } from "../runs/types";

export type SopEnvironment = {
  key: string;
  name_en: string;
  name_zh: string;
};

export type SopRunHistoryItem = {
  run_id: string;
  subject_id?: string | null;
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
