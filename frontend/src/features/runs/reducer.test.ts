import { describe, expect, it } from "vitest";

import {
  createInitialRunViewState,
  getOrderedNodeIds,
  reduceRunEvent,
} from "./reducer";
import type { RunEvent } from "./types";

describe("run event reducer", () => {
  it("marks a node running when a task starts", () => {
    const state = reduceRunEvent(
      createInitialRunViewState(),
      event({
        type: "tasks",
        node: "load_sop",
        sequence: 1,
        payload: { status: "started" },
      }),
    );

    expect(state.nodes.load_sop?.status).toBe("running");
    expect(state.nodes.load_sop?.firstSequence).toBe(1);
    expect(state.latestSequence).toBe(1);
  });

  it("appends message markdown text to the producing node", () => {
    const initial = createInitialRunViewState();
    const withFirstChunk = reduceRunEvent(
      initial,
      event({
        type: "messages",
        node: "check_steps",
        sequence: 2,
        payload: { delta: "**checking** " },
      }),
    );

    const state = reduceRunEvent(
      withFirstChunk,
      event({
        type: "messages",
        node: "check_steps",
        sequence: 3,
        payload: { delta: "steps" },
      }),
    );

    expect(state.nodes.check_steps?.streamText).toBe("**checking** steps");
  });

  it("stores update values and marks the node done", () => {
    const value = { checked_steps: 3 };
    const state = reduceRunEvent(
      createInitialRunViewState(),
      event({
        type: "updates",
        node: "check_steps",
        sequence: 4,
        payload: { value },
      }),
    );

    expect(state.nodes.check_steps?.status).toBe("done");
    expect(state.nodes.check_steps?.value).toEqual(value);
  });

  it("stores custom progress on the producing node", () => {
    const progress = { current: 2, total: 3 };
    const state = reduceRunEvent(
      createInitialRunViewState(),
      event({
        type: "custom",
        node: "check_steps",
        sequence: 5,
        payload: { progress },
      }),
    );

    expect(state.nodes.check_steps?.progress).toEqual(progress);
  });

  it("marks the run stopped when done arrives", () => {
    const state = reduceRunEvent(
      { ...createInitialRunViewState(), isRunning: true },
      event({
        type: "done",
        node: null,
        sequence: 6,
        payload: { status: "success" },
      }),
    );

    expect(state.isRunning).toBe(false);
    expect(state.latestSequence).toBe(6);
  });

  it("orders unknown nodes after registered nodes by first sequence", () => {
    const state = [
      event({ type: "tasks", node: "early_unknown", sequence: 8 }),
      event({ type: "tasks", node: "late_unknown", sequence: 10 }),
      event({ type: "tasks", node: "check_steps", sequence: 20 }),
      event({ type: "tasks", node: "load_sop", sequence: 30 }),
    ].reduce(reduceRunEvent, createInitialRunViewState());

    expect(
      getOrderedNodeIds(state, ["load_sop", "check_steps", "summarize_result"]),
    ).toEqual(["load_sop", "check_steps", "early_unknown", "late_unknown"]);
  });

  it("keeps the event sequence that first introduced an unknown node", () => {
    const state = [
      event({ type: "tasks", node: "z_late_unknown", sequence: 10 }),
      event({ type: "tasks", node: "a_early_unknown", sequence: 8 }),
    ].reduce(reduceRunEvent, createInitialRunViewState());

    expect(state.nodes.a_early_unknown?.firstSequence).toBe(8);
    expect(
      getOrderedNodeIds(state, ["load_sop", "check_steps", "summarize_result"]),
    ).toEqual(["a_early_unknown", "z_late_unknown"]);
  });
});

function event(overrides: Partial<RunEvent>): RunEvent {
  return {
    type: "tasks",
    node: "load_sop",
    thread_id: "quality-run:run-1",
    run_id: "run-1",
    sequence: 1,
    payload: { status: "started" },
    ...overrides,
  };
}
