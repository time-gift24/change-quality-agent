# Runs Frontend Design

Date: 2026-05-25

## Context

The frontend stack is fixed by `frontend/README.md`:

- Vite
- React 19
- TypeScript
- Tailwind CSS v4 through `@tailwindcss/vite`

The backend exposes SOP entry APIs and generic run observation APIs. The
frontend should mirror that split: `runs` is the reusable observation substrate,
and `sop` is the first business wrapper.

All frontend UI work must follow root `DESIGN.md`, generated from the Cohere
design system. The implementation must not invent a separate visual language.

## Goals

- Build a reusable run observer for any backend run.
- Render persisted SSE events from `/api/runs/{run_id}/events`.
- Use `Streamdown` for streamed markdown text.
- Keep SOP-specific fields out of generic run UI.
- Provide a thin SOP quality page that starts or joins runs.
- Preserve reconnect and replay behavior through event sequence cursors.

## Non-Goals

- Do not implement the final SOP quality report schema.
- Do not expose raw debug payloads by default.
- Do not create a custom markdown renderer.
- Do not make the SOP page own generic run state.

## Design System Requirements

The frontend must read and follow `DESIGN.md` before implementing UI. Required
interpretation for this product:

- Use `canvas`, `soft-stone`, and `border-light` for normal work surfaces.
- Use `primary`, `deep-green`, or `dark-navy` only for strong status bands,
  headers, or focused product panels.
- Use `action-blue` for links and precise secondary actions.
- Use `coral` sparingly for warning-like highlights or taxonomy accents.
- Use near-flat surfaces and thin rules; avoid decorative gradients and
  ornamental backgrounds.
- Keep cards practical and compact. Repeated run/event items may be cards;
  page sections should stay unframed.
- Use compact enterprise UI density for the run observer. This is an operating
  surface, not a marketing page.
- Map CSS custom properties used by Streamdown/shadcn-style components to the
  Cohere-inspired tokens in `DESIGN.md`.

## Architecture

Suggested directory structure:

```text
frontend/src/
  app/
    App.tsx
    routes.tsx
  styles/
    globals.css
  lib/
    apiClient.ts
    sse.ts
  features/
    runs/
      api.ts
      types.ts
      reducer.ts
      hooks.ts
      components/
        RunObserver.tsx
        RunStatusBar.tsx
        RunNodeList.tsx
        RunEventStream.tsx
        StreamMarkdown.tsx
    sop/
      api.ts
      types.ts
      hooks.ts
      pages/
        SopQualityPage.tsx
```

`features/runs` only knows generic run concepts:

- `run_id`
- `subject_type`
- `subject_id`
- `status`
- `current_node`
- `completed_nodes`
- `latest_sequence`
- normalized run events

It must not read or display `env_key` as a top-level generic run field.

`features/sop` owns SOP-specific concerns:

- environment selection
- SOP preview
- run creation
- `409 Conflict` join-existing-run behavior
- SOP run history

## Components

### `RunObserver`

Top-level generic run observation component.

Responsibilities:

- Fetch run summary with `useRun(runId)`.
- Subscribe to events with `useRunEvents(runId)`.
- Reduce events into node and event state.
- Render status, nodes, and event stream.
- Refresh run summary after terminal `done` or `error`.

### `RunStatusBar`

Displays stable run metadata:

- status
- subject type
- subject id
- current node
- started and finished time
- result status
- error summary

It must not display SOP environment as a generic top-level field.

### `RunNodeList`

Displays node runtime state in a stable order. Initial SOP node registry:

- `load_sop`
- `check_steps`
- `summarize_result`

Unknown nodes are appended after registered nodes, ordered by first event
sequence.

### `RunEventStream`

Displays the event timeline:

- `custom` events as concise progress rows
- `messages` events as streaming markdown
- `updates` events as expandable structured output
- `error` events as visible failure rows
- `checkpoints` events collapsed by default

### `StreamMarkdown`

Wraps the `Streamdown` component from the `streamdown` npm package.

Use it for `messages` event content and any event payload that is explicitly
markdown text. Do not use raw `dangerouslySetInnerHTML` or a homegrown markdown
renderer.

Expected usage shape:

```tsx
import { Streamdown } from "streamdown";
import "streamdown/styles.css";

export function StreamMarkdown({
  children,
  isStreaming,
}: {
  children: string;
  isStreaming: boolean;
}) {
  return (
    <Streamdown animated isAnimating={isStreaming}>
      {children}
    </Streamdown>
  );
}
```

Tailwind CSS v4 must scan Streamdown utilities from the frontend global CSS.
The path depends on dependency placement, but for `frontend/src/styles/globals.css`
and a frontend-local `node_modules`, use:

```css
@source "../../node_modules/streamdown/dist/*.js";
```

If dependencies are hoisted to the repository root, adjust the relative path
and document the choice in `frontend/README.md`.

### `SopQualityPage`

SOP-specific page that composes:

- SOP ID input
- environment selector
- preview button
- start quality run button
- SOP preview panel
- SOP run history list
- generic `RunObserver`

`409 Conflict` should not be treated as a hard page error. It should show a
short message and switch the observer to `active_run_id`.

## Event Reduction Model

Runtime state:

```ts
type NodeRuntime = {
  status: "idle" | "running" | "done" | "error" | "interrupted";
  streamText: string;
  value?: unknown;
  progress?: unknown;
  error?: string;
  firstSequence?: number;
};

type RunViewState = {
  latestSequence: number;
  nodes: Record<string, NodeRuntime>;
  events: RunEvent[];
  isRunning: boolean;
  connectionStatus: "idle" | "connecting" | "open" | "reconnecting" | "closed";
};
```

Reducer behavior:

- `tasks` starts, completes, fails, or interrupts nodes.
- `messages` appends markdown text to the producing node.
- `updates` stores node output and usually marks the node done.
- `custom` updates node progress and appends an event row.
- `checkpoints` updates debug metadata but stays collapsed.
- `error` marks the run terminal and visible failure.
- `done` marks the run terminal and triggers summary refresh.

## SSE Behavior

`useRunEvents` connects to:

```text
GET /api/runs/{run_id}/events?after={latestSequence}
```

Rules:

- Keep each browser tab's cursor local.
- Use the last received `sequence` for reconnect.
- Ignore heartbeat comments.
- Treat `done` and `error` as terminal.
- Do not clear prior events during reconnect.
- After terminal events, fetch `/api/runs/{run_id}` again for the final summary.

## Error Handling

- Run creation `202`: observe the returned `run_id`.
- Run creation `409`: observe `active_run_id`.
- SOP preview `404`: show missing SOP or environment.
- SOP preview `502`: show upstream SOP client failure.
- SSE reconnect: show a subtle reconnecting state without clearing output.
- Unknown event type: append to event stream as an unsupported event, but do not
  crash the observer.

## Testing Strategy

- Reducer tests for each event type.
- Hook tests for SSE cursor and terminal handling.
- Component tests for status, node ordering, and Streamdown rendering.
- SOP page tests for preview, start, conflict join, and history selection.
- Browser smoke test for desktop and mobile layouts.

## Open Decisions

- Whether to install Streamdown plugins such as `@streamdown/code`,
  `@streamdown/math`, or `@streamdown/mermaid`. V1 should install only
  `streamdown` unless a product requirement needs plugin rendering.
- Whether run workflow node registries come from backend metadata in a later
  API revision. V1 may keep a small frontend registry.
