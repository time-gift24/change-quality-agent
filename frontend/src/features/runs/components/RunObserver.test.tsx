// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  createInitialRunViewState,
  reduceRunEvent,
  type RunViewState,
} from "../reducer";
import type { RunEvent, RunSummary } from "../types";
import { RunEventStream } from "./RunEventStream";
import { RunNodeList } from "./RunNodeList";
import { RunObserver } from "./RunObserver";
import { RunStatusBar } from "./RunStatusBar";

const registeredNodeIds = ["load_sop", "check_steps", "summarize_result"];

afterEach(() => {
  cleanup();
});

describe("RunStatusBar", () => {
  it("displays status, subject type, and subject id", () => {
    render(<RunStatusBar summary={summary()} />);

    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getByText("sop")).toBeInTheDocument();
    expect(screen.getByText("payment-release")).toBeInTheDocument();
  });

  it("does not display env_key", () => {
    const summaryWithEnv = {
      ...summary(),
      env_key: "production",
    } as RunSummary & { env_key: string };

    render(<RunStatusBar summary={summaryWithEnv} />);

    expect(screen.queryByText("production")).not.toBeInTheDocument();
    expect(screen.queryByText("env_key")).not.toBeInTheDocument();
  });
});

describe("RunNodeList", () => {
  it("renders known nodes in registry order and unknown nodes by first event sequence", () => {
    const state = stateFromEvents([
      event({ node: "custom_lint", sequence: 1 }),
      event({ node: "summarize_result", sequence: 2 }),
      event({ node: "check_steps", sequence: 3 }),
      event({ node: "early_custom", sequence: 0 }),
      event({ node: "load_sop", sequence: 4 }),
    ]);

    render(
      <RunNodeList state={state} registeredNodeIds={registeredNodeIds} />,
    );

    const nodeItems = screen.getAllByRole("listitem").map((item) => {
      const nodeName = within(item).getByTestId("run-node-id");

      return nodeName.textContent;
    });

    expect(nodeItems).toEqual([
      "load_sop",
      "check_steps",
      "summarize_result",
      "early_custom",
      "custom_lint",
    ]);
  });
});

describe("RunEventStream", () => {
  it("renders accumulated node stream text as markdown", () => {
    const state = stateFromEvents([
      event({
        type: "messages",
        node: "check_steps",
        sequence: 1,
        payload: { delta: "**checking** " },
      }),
      event({
        type: "messages",
        node: "check_steps",
        sequence: 2,
        payload: { delta: "steps" },
      }),
    ]);

    render(<RunEventStream state={state} />);

    const eventRegion = screen.getByLabelText("Run events");

    expect(within(eventRegion).getByText("checking")).toBeInTheDocument();
    expect(within(eventRegion).getByText("steps")).toBeInTheDocument();
  });
});

describe("RunObserver", () => {
  it("shows reconnecting without clearing previous events", () => {
    const state: RunViewState = {
      ...stateFromEvents([
        event({
          type: "messages",
          node: "check_steps",
          sequence: 1,
          payload: { delta: "Previously streamed text" },
        }),
      ]),
      connectionStatus: "reconnecting",
    };

    render(
      <RunObserver
        summary={summary()}
        state={state}
        registeredNodeIds={registeredNodeIds}
      />,
    );

    expect(screen.getByText("reconnecting")).toBeInTheDocument();
    expect(screen.getByLabelText("Run events")).toHaveTextContent(
      "Previously streamed text",
    );
  });
});

function summary(overrides: Partial<RunSummary> = {}): RunSummary {
  return {
    run_id: "run-1",
    subject_type: "sop",
    subject_id: "payment-release",
    status: "running",
    current_node: "check_steps",
    completed_nodes: ["load_sop"],
    latest_sequence: 12,
    started_at: "2026-05-25T10:00:00Z",
    finished_at: null,
    result_status: null,
    error_summary: null,
    ...overrides,
  };
}

function stateFromEvents(events: RunEvent[]): RunViewState {
  return events.reduce(reduceRunEvent, createInitialRunViewState());
}

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
