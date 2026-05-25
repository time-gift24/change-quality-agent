import { useRun } from "../hooks";
import type { RunViewState } from "../reducer";
import type { RunSummary } from "../types";
import { RunEventStream } from "./RunEventStream";
import { RunNodeList } from "./RunNodeList";
import { RunStatusBar } from "./RunStatusBar";

type RunObserverProps = {
  runId: string;
  registeredNodeIds?: string[];
};

type RunObserverViewProps = {
  summary: RunSummary;
  state: RunViewState;
  registeredNodeIds?: string[];
};

const DEFAULT_REGISTERED_NODE_IDS = [
  "load_sop",
  "check_steps",
  "summarize_result",
];

export function RunObserver({
  runId,
  registeredNodeIds = DEFAULT_REGISTERED_NODE_IDS,
}: RunObserverProps) {
  const { summary, summaryError, summaryLoading, events } = useRun(runId);

  if (summaryError) {
    return (
      <section
        aria-label="Run observer"
        className="rounded-lg border border-[#e5e7eb] bg-white px-4 py-3 text-sm text-[#b30000]"
        role="alert"
      >
        {summaryError.message}
      </section>
    );
  }

  if (!summary) {
    return (
      <section
        aria-label="Run observer"
        className="rounded-lg border border-[#e5e7eb] bg-white px-4 py-3 text-sm text-[#616161]"
      >
        {summaryLoading ? "Loading run" : "Run unavailable"}
      </section>
    );
  }

  return (
    <RunObserverView
      summary={summary}
      state={events}
      registeredNodeIds={registeredNodeIds}
    />
  );
}

export function RunObserverView({
  summary,
  state,
  registeredNodeIds = DEFAULT_REGISTERED_NODE_IDS,
}: RunObserverViewProps) {
  return (
    <div className="space-y-3 bg-white text-[#212121]">
      <RunStatusBar
        summary={summary}
        connectionStatus={state.connectionStatus}
      />
      <div className="grid gap-3 lg:grid-cols-[minmax(220px,280px)_1fr]">
        <RunNodeList state={state} registeredNodeIds={registeredNodeIds} />
        <RunEventStream state={state} />
      </div>
    </div>
  );
}
