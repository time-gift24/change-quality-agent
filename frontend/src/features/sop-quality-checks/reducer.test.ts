import { describe, expect, it } from "vitest";

import {
  createInitialSopQualityCheckViewState,
  reduceSopQualityCheckEvent,
} from "./reducer";

describe("sop quality check reducer", () => {
  it("tracks lifecycle event sequence without payload", () => {
    const state = reduceSopQualityCheckEvent(
      createInitialSopQualityCheckViewState(),
      {
        check_id: "check-1",
        sequence: 2,
        type: "checkpoint",
        node: "check_steps",
        checkpoint_id: "checkpoint-1",
        task_id: null,
        message: "Checkpoint saved.",
      },
    );

    expect(state.latestSequence).toBe(2);
    expect(state.needsRefresh).toBe(true);
  });
});
