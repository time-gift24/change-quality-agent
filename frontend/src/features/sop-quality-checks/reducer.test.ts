import { describe, expect, it } from "vitest";

import {
  createInitialSessionViewState,
  type SessionViewState,
} from "../sessions/reducer";
import {
  createInitialSopQualityCheckViewState,
  projectSessionStateToSopView,
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
        node: "review_sop",
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
      node: "review_sop",
      checkpoint_id: null,
      task_id: null,
      message: "Hello ",
    });

    const second = reduceSopQualityCheckEvent(first, {
      check_id: "check-1",
      sequence: 2,
      type: "messages",
      node: "review_sop",
      checkpoint_id: null,
      task_id: null,
      message: "world",
    });

    expect(second.latestSequence).toBe(2);
    expect(second.needsRefresh).toBe(false);
    expect(second.nodes.review_sop).toMatchObject({
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
      node: "review_sop",
      checkpoint_id: null,
      task_id: null,
      message: "正在分析 SOP...",
    });

    const summary = reduceSopQualityCheckEvent(thinking, {
      check_id: "check-1",
      sequence: 2,
      type: "messages",
      channel: "summary",
      node: "review_sop",
      checkpoint_id: null,
      task_id: null,
      message: "## SOP Quality Report",
    });

    expect(summary.nodes.review_sop).toMatchObject({
      status: "running",
      thinkingText: "正在分析 SOP...",
      streamText: "## SOP Quality Report",
    });
  });

  describe("projectSessionStateToSopView", () => {
    it("projects session messages grouped by step into SOP nodes", () => {
      const sessionState: SessionViewState = createInitialSessionViewState();
      sessionState.messages = [
        {
          id: "msg-1",
          session_id: 1,
          sequence: 1,
          role: "assistant",
          content: "loaded sop content",
          additional_kwargs: { step: "load_sop", kind: "step_message" },
          created_at: "",
        },
        {
          id: "msg-2",
          session_id: 1,
          sequence: 2,
          role: "assistant",
          content: "review result",
          additional_kwargs: { step: "review_sop", kind: "step_message" },
          created_at: "",
        },
      ];

      const result = projectSessionStateToSopView(sessionState);

      expect(result.nodes.load_sop).toMatchObject({
        status: "done",
        streamText: "loaded sop content",
      });
      expect(result.nodes.review_sop).toMatchObject({
        status: "done",
        streamText: "review result",
      });
      expect(result.latestSequence).toBe(2);
    });

    it("marks last step as running when isRunning is true", () => {
      const sessionState: SessionViewState = createInitialSessionViewState();
      sessionState.messages = [
        {
          id: "msg-1",
          session_id: 1,
          sequence: 1,
          role: "assistant",
          content: "loaded",
          additional_kwargs: { step: "load_sop" },
          created_at: "",
        },
        {
          id: "msg-2",
          session_id: 1,
          sequence: 2,
          role: "assistant",
          content: "reviewing...",
          additional_kwargs: { step: "review_sop" },
          created_at: "",
        },
      ];

      const result = projectSessionStateToSopView(sessionState, true);

      expect(result.nodes.load_sop.status).toBe("done");
      expect(result.nodes.review_sop.status).toBe("running");
    });

    it("uses liveBuffers for running steps", () => {
      const sessionState: SessionViewState = createInitialSessionViewState();
      sessionState.messages = [
        {
          id: "msg-1",
          session_id: 1,
          sequence: 1,
          role: "assistant",
          content: "loaded",
          additional_kwargs: { step: "load_sop" },
          created_at: "",
        },
      ];
      sessionState.liveBuffers = {
        "step:review_sop": "streaming text...",
      };
      sessionState.thinking = { "step:review_sop": true };

      const result = projectSessionStateToSopView(sessionState, true);

      expect(result.nodes.review_sop).toMatchObject({
        status: "running",
        streamText: "streaming text...",
        thinkingText: "思考中",
      });
    });

    it("ignores messages without step", () => {
      const sessionState: SessionViewState = createInitialSessionViewState();
      sessionState.messages = [
        {
          id: "msg-1",
          session_id: 1,
          sequence: 1,
          role: "user",
          content: "orphan",
          additional_kwargs: {},
          created_at: "",
        },
      ];

      const result = projectSessionStateToSopView(sessionState);

      expect(Object.keys(result.nodes)).toHaveLength(0);
    });
  });
});
