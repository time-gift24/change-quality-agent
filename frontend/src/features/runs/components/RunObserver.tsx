import type { RunViewState } from "../reducer";
import type { RunSummary } from "../types";
import { RunEventStream } from "./RunEventStream";
import { RunNodeList } from "./RunNodeList";
import { RunStatusBar } from "./RunStatusBar";

type RunObserverProps = {
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
  summary,
  state,
  registeredNodeIds = DEFAULT_REGISTERED_NODE_IDS,
}: RunObserverProps) {
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
