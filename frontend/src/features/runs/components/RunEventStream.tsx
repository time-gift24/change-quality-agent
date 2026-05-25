import type { RunViewState } from "../reducer";
import type { RunEvent } from "../types";
import { StreamMarkdown } from "./StreamMarkdown";

type RunEventStreamProps = {
  state: RunViewState;
};

export function RunEventStream({ state }: RunEventStreamProps) {
  const visibleEvents = getVisibleEvents(state.events);

  return (
    <section
      aria-label="Run events"
      className="rounded-lg border border-[#e5e7eb] bg-white"
    >
      <div className="border-b border-[#e5e7eb] px-4 py-3">
        <h2 className="m-0 text-sm font-medium text-[#212121]">Events</h2>
      </div>
      <ol className="m-0 list-none divide-y divide-[#e5e7eb] p-0">
        {visibleEvents.map((event) => (
          <li className="px-4 py-3 text-sm" key={event.sequence}>
            <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[#616161]">
              <span>#{event.sequence}</span>
              <span>{event.type}</span>
              {event.node ? <span>{event.node}</span> : null}
            </div>
            <EventPayload event={event} state={state} />
          </li>
        ))}
        {visibleEvents.length === 0 ? (
          <li className="px-4 py-3 text-sm text-[#616161]">No events yet</li>
        ) : null}
      </ol>
    </section>
  );
}

function EventPayload({
  event,
  state,
}: {
  event: RunEvent;
  state: RunViewState;
}) {
  if (event.type === "messages" && event.node) {
    const text = state.nodes[event.node]?.streamText ?? "";

    return (
      <div className="text-[#212121]">
        <StreamMarkdown
          isStreaming={
            state.isRunning && state.nodes[event.node]?.status === "running"
          }
        >
          {text}
        </StreamMarkdown>
      </div>
    );
  }

  if (event.type === "error") {
    return (
      <p className="m-0 text-[#b30000]">
        {stringPayloadValue(event, "error") ??
          stringPayloadValue(event, "message") ??
          "Run event failed"}
      </p>
    );
  }

  if (event.type === "custom") {
    return (
      <p className="m-0 text-[#212121]">
        {progressText(event) ?? formatPayload(event.payload)}
      </p>
    );
  }

  if (event.type === "updates" || event.type === "checkpoints") {
    return (
      <details className="text-[#212121]">
        <summary className="cursor-pointer text-[#1863dc]">Details</summary>
        <pre className="mt-2 max-h-64 overflow-auto rounded border border-[#e5e7eb] bg-[#eeece7] p-3 text-xs">
          {formatPayload(event.payload)}
        </pre>
      </details>
    );
  }

  return (
    <p className="m-0 text-[#616161]">
      {stringPayloadValue(event, "status") ?? event.type}
    </p>
  );
}

function getVisibleEvents(events: RunEvent[]): RunEvent[] {
  const seenMessageNodes = new Set<string>();
  const visibleEvents: RunEvent[] = [];

  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];

    if (event.type === "messages" && event.node) {
      if (seenMessageNodes.has(event.node)) {
        continue;
      }

      seenMessageNodes.add(event.node);
    }

    visibleEvents.push(event);
  }

  return visibleEvents.reverse();
}

function stringPayloadValue(event: RunEvent, key: string): string | undefined {
  const value = event.payload[key];

  return typeof value === "string" ? value : undefined;
}

function progressText(event: RunEvent): string | undefined {
  const progress = event.payload.progress;

  if (typeof progress === "string") {
    return progress;
  }

  if (typeof progress === "number" || typeof progress === "boolean") {
    return String(progress);
  }

  if (isProgressObject(progress)) {
    return `${progress.current} / ${progress.total}`;
  }

  return (
    stringPayloadValue(event, "message") ??
    stringPayloadValue(event, "status")
  );
}

function isProgressObject(
  value: unknown,
): value is { current: string | number; total: string | number } {
  return (
    typeof value === "object" &&
    value !== null &&
    "current" in value &&
    "total" in value &&
    (typeof value.current === "string" || typeof value.current === "number") &&
    (typeof value.total === "string" || typeof value.total === "number")
  );
}

function formatPayload(payload: Record<string, unknown>): string {
  return JSON.stringify(payload, null, 2);
}
