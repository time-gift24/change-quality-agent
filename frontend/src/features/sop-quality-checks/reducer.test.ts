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

  it("appends streamed message deltas to the node output", () => {
    const initial = createInitialSopQualityCheckViewState();
    const first = reduceSopQualityCheckEvent(initial, {
      check_id: "check-1",
      sequence: 2,
      type: "messages",
      node: "check_steps",
      checkpoint_id: null,
      task_id: null,
      message: "Hello ",
    });

    const second = reduceSopQualityCheckEvent(first, {
      check_id: "check-1",
      sequence: 2,
      type: "messages",
      node: "check_steps",
      checkpoint_id: null,
      task_id: null,
      message: "world",
    });

    expect(second.latestSequence).toBe(2);
    expect(second.needsRefresh).toBe(false);
    expect(second.nodes.check_steps).toMatchObject({
      status: "running",
      streamText: "Hello world",
      firstSequence: 2,
    });
  });

  it("keeps thinking and summary channels separate", () => {
    const initial = createInitialSopQualityCheckViewState();
    const thinking = reduceSopQualityCheckEvent(initial, {
      check_id: "check-1",
      sequence: 2,
      type: "messages",
      channel: "thinking",
      node: "check_steps",
      checkpoint_id: null,
      task_id: null,
      message: "正在分析 SOP...",
    });

    const summary = reduceSopQualityCheckEvent(thinking, {
      check_id: "check-1",
      sequence: 2,
      type: "messages",
      channel: "summary",
      node: "check_steps",
      checkpoint_id: null,
      task_id: null,
      message: "## SOP Quality Report",
    });

    expect(summary.nodes.check_steps).toMatchObject({
      status: "running",
      thinkingText: "正在分析 SOP...",
      streamText: "## SOP Quality Report",
    });
  });
});
