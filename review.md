# Code Review — `codex/add-cohere-design` (PR #1)

## Scope
Diff vs `origin/main`: 38 files / +10,449 LoC. Mostly new frontend under
`frontend/src/features/runs`, `frontend/src/features/sop`, `frontend/src/lib`,
`frontend/src/app`, plus `DESIGN.md` and two plan docs.

PR: https://github.com/time-gift24/change-quality-agent/pull/1

Method: 3 finder angles (line-by-line / removed-behavior / cross-file tracer)
→ dedup → 1-vote verify against the actual files (frontend source AND backend
handlers in `app/api/v1/sop.py`, `app/api/v1/runs.py`, schemas in
`app/schemas/`). Recall-biased: REFUTED only when constructible from code.

---

## Findings (most severe first)

### 1. CRITICAL — `getSopRunHistory` envelope mismatch crashes the History panel
**File:** `frontend/src/features/sop/api.ts:84`

The frontend does `requestJson<{ runs: SopRunHistoryItem[] }>(…)` and returns
`response.runs`, but the backend `GET /api/sop/{sop_id}/runs` returns a bare
`list[RunSummary]` (see `app/api/v1/sop.py:100-109`).

**Failure:** `useSopRunHistory` ends up with `state.data === undefined`;
`RunHistory` reads `runs.length` and throws
`TypeError: Cannot read properties of undefined (reading 'length')`, unmounting
the page. The Vitest suites pass because they mock `getSopRunHistory` directly.

**Fix sketch:**
```ts
return requestJson<SopRunHistoryItem[]>(buildSopRunsUrl(sopId, envKey));
```

---

### 2. CRITICAL — SOP preview reads non-existent `raw_payload` field
**File:** `frontend/src/features/sop/pages/SopQualityPage.tsx:299`, `frontend/src/features/sop/types.ts:9-14`

`SopPreviewPanel` renders `JSON.stringify(preview.raw_payload ?? preview, …)`
and `getPreviewTitle` reads `payload.title`. The backend returns
`SopSnapshot { sop_id, env_key, source_version, updated_at, payload }`
(`app/schemas/sop.py:13-18`). There is no `raw_payload` and no top-level `title`.

**Failure:**
1. The fallback dumps the entire `SopSnapshot`, including `env_key` and
   `source_version` — the design says generic UI must not expose these.
2. `getPreviewTitle` always falls through to the `"SOP preview"` placeholder.

**Fix sketch:** rename the type/field to `payload`, render `preview.payload`,
read `preview.payload.title` for the heading.

---

### 3. CRITICAL — Infinite SSE reconnect loop for terminal/historical runs
**File:** `frontend/src/features/runs/hooks.ts:233-252`

`onerror` unconditionally schedules a 1-second reconnect, with no backoff and
no attempt cap. `isTerminal` is only set when a `done`/`error` event arrives.

Pair this with the backend: `app/api/v1/runs.py:60-66` — when the requested
run is already terminal and `get_events_after` returns no rows, the generator
returns immediately, so `EventSource` fires `error` (no terminal event sent).

**Failure:** opening any completed run from history opens the SSE → backend
closes the empty stream → `error` → reconnect at 1 req/s indefinitely.

**Fix sketch:** if the run summary status is already terminal, don't open the
stream (or close on first `error` when the summary says terminal). Add backoff
+ attempt cap regardless.

---

### 4. HIGH — `useRun` seeds the cursor with `latest_sequence`, hiding all prior events
**File:** `frontend/src/features/runs/hooks.ts:74-76`

```ts
setEventsInitialAfter((current) =>
  current === undefined ? nextSummary.latest_sequence : current,
);
```

**Failure:** opening any non-fresh run (mid-stream join, history click) skips
every event up to the current sequence. RunNodeList shows previously-streaming
nodes with empty `streamText`; nodes whose `updates` event was at sequence
≤`latest_sequence` stay `status='idle'` instead of `'done'`. Combined with
finding #3 the page also never settles.

**Fix sketch:** seed with `0` (or `undefined` so the URL omits `after`) and let
the cursor advance as events arrive. Backend already supports `after=0`.

---

### 5. HIGH — Streamed-message rows remount on every chunk (key flicker)
**File:** `frontend/src/features/runs/components/RunEventStream.tsx:22, 98-117`

`getVisibleEvents` keeps only the latest `messages` event per node, but the
`<li>` is keyed by `event.sequence`. Each new chunk has a new sequence → new
key → React reconciles a new node → `StreamMarkdown`'s Streamdown animation
state resets every chunk.

**Fix sketch:**
```tsx
key={event.type === "messages" && event.node ? `m:${event.node}` : `e:${event.sequence}`}
```

---

### 6. MEDIUM — `updates` event masks failed nodes
**File:** `frontend/src/features/runs/reducer.ts:110-121`

`updates` unconditionally sets `status: "done"`. If a `tasks` event already
marked the node `status='error'` / `'interrupted'`, a later (or out-of-order
replayed) `updates` event flips it back to `done`.

**Fix sketch:** preserve terminal failure states:
```ts
status: node.status === "error" || node.status === "interrupted" ? node.status : "done",
```

---

### 7. MEDIUM — Run-level `done` leaves still-running nodes stuck on "running"
**File:** `frontend/src/features/runs/reducer.ts:47-53`

When a node was streaming `messages` (status=`running`) and the run terminates
with a `done` event before any `tasks completed` / `updates` arrives for that
node, `state.isRunning` becomes false but the node status stays `running`
indefinitely. RunNodeList then shows `running` next to a finished run.

**Fix sketch:** in the `done` branch, walk `nodes` and demote any `running`
nodes to `done` (or to `interrupted` if you want to be conservative).

---

### 8. MEDIUM — `taskError` wipes a previously stored error
**File:** `frontend/src/features/runs/reducer.ts:224-233` (also line 88-92)

A redundant `tasks` event with `{status: "failed"}` and no `error` key resets
`node.error` to `undefined` even though `status` stays `error`. The status bar
shows the failure status without the explanatory message.

**Fix sketch:**
```ts
const nextError = stringPayloadValue(event, "error");
return { ...node, status: nextStatus, error: nextError ?? node.error };
```

---

### 9. MEDIUM — `requestJson` throws away response body, hiding backend reasons
**File:** `frontend/src/lib/apiClient.ts:13-15`

`ApiError` only carries `status` and `statusText`. FastAPI's `HTTPException`
puts the reason in `body.detail`. So a 502 from `SopClientError` and a 404
from `SopNotFoundError` both surface as `"API request failed: 404 Not Found"` /
`"API request failed: 502 Bad Gateway"`. `ActiveRunConflict.message` is
similarly hidden for any caller that doesn't special-case 409 (only
`startSopQualityRun` does).

**Fix sketch:** read `await response.text()` (or `.json()` with a try/catch)
and attach to `ApiError.detail`. Render `error.detail ?? error.statusText`.

---

### 10. LOW — Start-run race overwrites a user's history pick
**File:** `frontend/src/features/sop/pages/SopQualityPage.tsx:74-83`

The handler guards on `startRequestRef`, `sopId`, and `selectedEnv`, but if
the user clicks `Start run`, then clicks a history item `B` while the request
is in flight, none of those guards trip. When the start resolves with a new
run `C`, `setObservedRunId(result.runId)` silently replaces the user's pick.

**Fix sketch:** capture `observedRunIdRef.current` at request start; bail if
`observedRunId` changed since.

---

## Verification status

| # | Finding | Status | Evidence |
|---|---------|--------|----------|
| 1 | history envelope mismatch | **CONFIRMED** | `app/api/v1/sop.py:100-109` returns `list[RunSummary]`; frontend reads `response.runs` |
| 2 | preview field mismatch | **CONFIRMED** | `app/schemas/sop.py:13-18` defines `payload`; frontend reads `raw_payload` |
| 3 | infinite SSE reconnect on terminal runs | **CONFIRMED** | `app/api/v1/runs.py:60-66` + `hooks.ts:233-252` |
| 4 | cursor seeded from `latest_sequence` | **CONFIRMED** | `hooks.ts:74-76` |
| 5 | messages-event key flicker | **CONFIRMED** | `RunEventStream.tsx:22` + `:98-117` |
| 6 | `updates` overrides error | **PLAUSIBLE** | `reducer.ts:114-118` — depends on out-of-order/replay; no guard exists |
| 7 | `done` leaves running nodes | **PLAUSIBLE** | `reducer.ts:47-53` |
| 8 | `taskError` wipes prior error | **PLAUSIBLE** | `reducer.ts:88-92, 224-233` |
| 9 | apiClient discards body | **CONFIRMED** | `apiClient.ts:13-15` |
| 10 | start-vs-history-pick race | **CONFIRMED** | `SopQualityPage.tsx:74-83` — guard does not include `observedRunId` |

## Recommended merge gate
- Block on #1, #2, #3, #4 — they make the SOP page unusable end-to-end against
  the real backend (Vitest passes only because every API is mocked).
- Cluster #5, #6, #7, #8 in one reducer/UI patch — small, mechanical fixes.
- Defer #9, #10 to a follow-up if needed; both are UX-level.
