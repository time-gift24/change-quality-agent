// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { SopQualityCheckObserverView } from "./SopQualityCheckObserver";
import type { SopQualityCheckViewState } from "../reducer";
import type { SopQualityCheckDetail } from "../types";

describe("SopQualityCheckObserverView", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders user-facing node labels instead of internal node ids", () => {
    render(
      <SopQualityCheckObserverView
        detail={detail()}
        state={{
          ...viewState(),
          nodes: {
            load_sop: {
              status: "done",
              streamText: "SOP snapshot loaded.",
            },
          },
        }}
      />,
    );

    expect(screen.getByText("读取 SOP")).toBeInTheDocument();
    expect(screen.queryByText("load_sop")).not.toBeInTheDocument();
  });

  it("renders thinking status separately from summary output", () => {
    render(
      <SopQualityCheckObserverView
        detail={detail()}
        state={{
          ...viewState(),
          nodes: {
            check_steps: {
              status: "running",
              thinkingText: "正在分析 SOP...",
              streamText: "## SOP Quality Report",
            },
          },
        }}
      />,
    );

    expect(screen.getByText("思考")).toBeInTheDocument();
    expect(screen.getByText("正在分析 SOP...")).toBeInTheDocument();
    expect(
      screen.getAllByText(
        (_, element) => element?.textContent === "SOP Quality Report",
      ).length,
    ).toBeGreaterThan(0);
  });
});

function detail(): SopQualityCheckDetail {
  return {
    check_id: "check-1",
    sop_id: "release-checklist",
    env_key: "dev",
    status: "running",
    latest_sequence: 1,
    current_checkpoint_id: null,
    result: null,
    error: null,
    display_state: {
      latest_sequence: 1,
      nodes: {},
      is_running: true,
    },
  };
}

function viewState(): SopQualityCheckViewState {
  return {
    latestSequence: 1,
    nodes: {},
    events: [],
    needsRefresh: false,
    isRunning: true,
    connectionStatus: "open",
  };
}
