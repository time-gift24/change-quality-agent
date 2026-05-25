# Runs Frontend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a React frontend for observing generic runs and starting SOP quality runs, using Streamdown for streamed markdown output and the Cohere-inspired `DESIGN.md` system for UI.

**Architecture:** The frontend has a reusable `features/runs` substrate for run summaries, SSE events, reducers, hooks, and observer components. `features/sop` is a thin business wrapper for environments, SOP preview, run start, conflict join, and history. Streamed `messages` content is rendered through `Streamdown`, not raw text or a custom markdown renderer.

**Tech Stack:** Vite, React 19, TypeScript, Tailwind CSS v4 with `@tailwindcss/vite`, Streamdown, Vitest, React Testing Library, Playwright.

**Implemented UI contract:** `DESIGN.md` is mandatory for UI work. The app uses
the restrained workbench shell in `frontend/src/app/App.tsx`, route composition
in `frontend/src/app/routes.tsx`, frontend-local Streamdown scanning through
`@source "../../node_modules/streamdown/dist/*.js"`, and `StreamMarkdown` inside
`RunEventStream` for streamed markdown messages. Generic run UI does not expose
SOP `env_key`; the SOP page remains a thin wrapper over `RunObserver`.

---

### Task 1: Verify Frontend Design Inputs

**Files:**
- Read: `DESIGN.md`
- Read: `frontend/README.md`
- Read: `docs/plans/2026-05-25-runs-frontend-design.md`
- Read: `docs/plans/2026-05-25-sop-runs-api-design.md`
- Modify: `frontend/README.md`

**Step 1: Confirm design stack**

Read the files above and confirm:

- frontend stack is Vite + React 19 + TypeScript + Tailwind CSS v4
- UI must follow root `DESIGN.md`
- stream output must use `Streamdown`
- generic `/api/runs/{run_id}` UI must not expose top-level `env_key`

**Step 2: Update stale README plan reference**

Update `frontend/README.md` so it points to:

```text
docs/plans/2026-05-25-runs-frontend-implementation.md
```

Add:

```markdown
Before implementing UI, read `../DESIGN.md` and follow it strictly.
Streamed markdown output must be rendered with `streamdown`.
Run message events must be rendered by `RunEventStream` through
`StreamMarkdown`, which wraps `streamdown`.
```

**Step 3: Commit**

```bash
git add frontend/README.md
git commit -m "docs: align frontend implementation references"
```

### Task 2: Scaffold Vite React App

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/app/App.tsx`
- Create: `frontend/src/styles/globals.css`

**Step 1: Create package metadata**

Create `frontend/package.json` with:

```json
{
  "name": "change-quality-agent-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest run",
    "test:watch": "vitest",
    "preview": "vite preview"
  },
  "dependencies": {
    "@tailwindcss/vite": "latest",
    "@vitejs/plugin-react": "latest",
    "tailwindcss": "latest",
    "typescript": "latest",
    "vite": "latest",
    "react": "latest",
    "react-dom": "latest",
    "streamdown": "latest"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "latest",
    "@testing-library/react": "latest",
    "@types/react": "latest",
    "@types/react-dom": "latest",
    "jsdom": "latest",
    "vitest": "latest",
    "playwright": "latest"
  }
}
```

**Step 2: Configure Vite and Tailwind**

In `frontend/vite.config.ts`, add `react()` and `tailwindcss()` plugins.

In `frontend/src/styles/globals.css`, include:

```css
@import "tailwindcss";
@source "../../node_modules/streamdown/dist/*.js";
@import "streamdown/styles.css";
```

Add CSS custom properties mapped from `DESIGN.md`, including:

```css
:root {
  --background: #ffffff;
  --foreground: #212121;
  --card: #ffffff;
  --card-foreground: #212121;
  --muted: #eeece7;
  --muted-foreground: #616161;
  --border: #e5e7eb;
  --input: #e5e7eb;
  --primary: #17171c;
  --primary-foreground: #ffffff;
  --radius: 8px;
}
```

**Step 3: Install dependencies**

Run:

```bash
cd frontend
npm install
```

Expected: `package-lock.json` is created.

**Step 4: Build baseline**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend
git commit -m "feat: scaffold React frontend"
```

### Task 3: Add Generic Run Types and API Client

**Files:**
- Create: `frontend/src/lib/apiClient.ts`
- Create: `frontend/src/features/runs/types.ts`
- Create: `frontend/src/features/runs/api.ts`
- Test: `frontend/src/features/runs/api.test.ts`

**Step 1: Write failing tests**

Create tests that assert:

- `RunSummary` does not include top-level `env_key`
- `buildRunEventsUrl("run-1", 12)` returns `/api/runs/run-1/events?after=12`
- run API functions call generic `/api/runs` endpoints

**Step 2: Run tests**

```bash
cd frontend
npm run test -- src/features/runs/api.test.ts
```

Expected: FAIL.

**Step 3: Implement types and API**

Define:

```ts
export type RunStatus =
  | "pending"
  | "running"
  | "success"
  | "error"
  | "timeout"
  | "interrupted";

export type RunSummary = {
  run_id: string;
  subject_type: string;
  subject_id: string;
  status: RunStatus;
  current_node: string | null;
  completed_nodes: string[];
  latest_sequence: number;
  started_at?: string | null;
  finished_at?: string | null;
  result_status?: string | null;
  error_summary?: string | null;
};

export type RunEvent = {
  type: "tasks" | "messages" | "updates" | "custom" | "checkpoints" | "error" | "done";
  node: string | null;
  thread_id: string;
  run_id: string;
  checkpoint_id?: string | null;
  sequence: number;
  payload: Record<string, unknown>;
};
```

**Step 4: Verify tests**

```bash
cd frontend
npm run test -- src/features/runs/api.test.ts
```

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/lib frontend/src/features/runs
git commit -m "feat: add run API types"
```

### Task 4: Add Run Event Reducer

**Files:**
- Create: `frontend/src/features/runs/reducer.ts`
- Test: `frontend/src/features/runs/reducer.test.ts`

**Step 1: Write failing reducer tests**

Test:

- `tasks` started marks a node running
- `messages` appends markdown text
- `updates` stores node value and marks done
- `custom` stores progress
- `done` marks `isRunning` false
- unknown nodes append after registered nodes by first sequence

**Step 2: Run tests**

```bash
cd frontend
npm run test -- src/features/runs/reducer.test.ts
```

Expected: FAIL.

**Step 3: Implement reducer**

Implement state and reducer from `docs/plans/2026-05-25-runs-frontend-design.md`.
Do not add SOP-specific fields to run state.

**Step 4: Verify tests**

```bash
cd frontend
npm run test -- src/features/runs/reducer.test.ts
```

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/features/runs/reducer.ts frontend/src/features/runs/reducer.test.ts
git commit -m "feat: add run event reducer"
```

### Task 5: Add SSE Hook With Reconnect Cursor

**Files:**
- Create: `frontend/src/lib/sse.ts`
- Create: `frontend/src/features/runs/hooks.ts`
- Test: `frontend/src/features/runs/hooks.test.tsx`

**Step 1: Write failing hook tests**

Test:

- connects with `after=latestSequence`
- updates local cursor from event `id` or event `sequence`
- ignores heartbeat comments
- reconnect keeps prior events
- terminal `done` or `error` closes stream and triggers summary refresh

**Step 2: Run tests**

```bash
cd frontend
npm run test -- src/features/runs/hooks.test.tsx
```

Expected: FAIL.

**Step 3: Implement hooks**

Implement:

- `useRun(runId)`
- `useRunEvents(runId, initialAfter)`
- `createRunEventSource(url)`

Use native `EventSource` for SSE. Keep reconnect cursor in React state or a
ref. Do not mutate backend state from the SSE hook.

**Step 4: Verify tests**

```bash
cd frontend
npm run test -- src/features/runs/hooks.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/lib/sse.ts frontend/src/features/runs/hooks.ts frontend/src/features/runs/hooks.test.tsx
git commit -m "feat: add run SSE hooks"
```

### Task 6: Add Streamdown-Based Markdown Component

**Files:**
- Create: `frontend/src/features/runs/components/StreamMarkdown.tsx`
- Test: `frontend/src/features/runs/components/StreamMarkdown.test.tsx`

**Step 1: Write failing component test**

Test that markdown text renders through the `StreamMarkdown` component:

```tsx
render(<StreamMarkdown isStreaming>**checking** steps</StreamMarkdown>);
expect(screen.getByText("checking")).toBeInTheDocument();
```

**Step 2: Run test**

```bash
cd frontend
npm run test -- src/features/runs/components/StreamMarkdown.test.tsx
```

Expected: FAIL.

**Step 3: Implement component**

Use:

```tsx
import { Streamdown } from "streamdown";

export function StreamMarkdown({
  children,
  isStreaming,
}: {
  children: string;
  isStreaming?: boolean;
}) {
  return (
    <Streamdown animated isAnimating={Boolean(isStreaming)}>
      {children}
    </Streamdown>
  );
}
```

Do not use `dangerouslySetInnerHTML`.

**Step 4: Verify test**

```bash
cd frontend
npm run test -- src/features/runs/components/StreamMarkdown.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/features/runs/components/StreamMarkdown.tsx frontend/src/features/runs/components/StreamMarkdown.test.tsx
git commit -m "feat: add Streamdown markdown renderer"
```

### Task 7: Add Run Observer Components

**Files:**
- Create: `frontend/src/features/runs/components/RunObserver.tsx`
- Create: `frontend/src/features/runs/components/RunStatusBar.tsx`
- Create: `frontend/src/features/runs/components/RunNodeList.tsx`
- Create: `frontend/src/features/runs/components/RunEventStream.tsx`
- Test: `frontend/src/features/runs/components/RunObserver.test.tsx`

**Step 1: Write failing component tests**

Test:

- `RunStatusBar` displays status, subject type, and subject id
- `RunStatusBar` does not display `env_key`
- `RunNodeList` renders known nodes in registry order
- `RunEventStream` uses `StreamMarkdown` for message events
- `RunObserver` shows reconnecting without clearing previous events

**Step 2: Run tests**

```bash
cd frontend
npm run test -- src/features/runs/components/RunObserver.test.tsx
```

Expected: FAIL.

**Step 3: Implement components**

Apply `DESIGN.md`:

- white/stone surfaces
- thin border rules
- practical 8px card radius
- compact status rows
- no decorative gradients
- action-blue links

`RunEventStream` must render `messages` event accumulated text through
`StreamMarkdown`.

**Step 4: Verify tests**

```bash
cd frontend
npm run test -- src/features/runs/components/RunObserver.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/features/runs/components
git commit -m "feat: add generic run observer UI"
```

### Task 8: Add SOP Page Wrapper

**Files:**
- Create: `frontend/src/features/sop/types.ts`
- Create: `frontend/src/features/sop/api.ts`
- Create: `frontend/src/features/sop/hooks.ts`
- Create: `frontend/src/features/sop/pages/SopQualityPage.tsx`
- Test: `frontend/src/features/sop/pages/SopQualityPage.test.tsx`

**Step 1: Write failing SOP tests**

Test:

- environments load into selector
- preview fetch does not create a run
- `202` starts observing returned run
- `409` switches to `active_run_id`
- history click switches observer run

**Step 2: Run tests**

```bash
cd frontend
npm run test -- src/features/sop/pages/SopQualityPage.test.tsx
```

Expected: FAIL.

**Step 3: Implement SOP page**

Compose SOP-specific controls with generic `RunObserver`. Keep SOP `env` in the
SOP form and history area only. Do not pass `env_key` into generic run UI.
The page should stay a thin business wrapper; generic run summary, nodes, and
streaming output remain owned by `RunObserver`.

**Step 4: Verify tests**

```bash
cd frontend
npm run test -- src/features/sop/pages/SopQualityPage.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/features/sop
git commit -m "feat: add SOP quality page"
```

### Task 9: Add App Shell and Routes

**Files:**
- Modify: `frontend/src/app/App.tsx`
- Create: `frontend/src/app/routes.tsx`
- Test: `frontend/src/app/App.test.tsx`

**Step 1: Write failing app test**

Test that the root app renders `SopQualityPage`.

**Step 2: Run test**

```bash
cd frontend
npm run test -- src/app/App.test.tsx
```

Expected: FAIL.

**Step 3: Implement app shell**

Use a restrained workbench layout that follows `DESIGN.md`:

- white canvas
- compact top title row
- thin dividers
- no marketing hero
- no decorative orbs or gradients

**Step 4: Verify test**

```bash
cd frontend
npm run test -- src/app/App.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/app
git commit -m "feat: add frontend app shell"
```

### Task 10: Browser Verification

**Files:**
- Verify frontend behavior

**Step 1: Run full frontend checks**

```bash
cd frontend
npm run test
npm run build
```

Expected: PASS.

**Step 2: Start dev server**

```bash
cd frontend
npm run dev
```

Expected: Vite serves the app.

**Step 3: Verify in browser**

Use browser automation to check:

- desktop layout has no overlapping UI
- mobile layout has no overlapping UI
- run observer can display mocked event fixtures
- streamed markdown appears through Streamdown styling
- status, node list, and event stream follow `DESIGN.md`

Recorded verification for the implemented frontend:

- `npm run test` passed for 7 files / 49 tests.
- `npm run build` passed with only the existing Vite chunk-size warning.
- Dev server served the app at `http://127.0.0.1:5174/`.
- Browser checks covered desktop and mobile layout, mocked `/api/sop`,
  `/api/runs`, named SSE events, and Streamdown DOM evidence including
  headings, strong text, and inline code.

**Step 4: Commit fixes if needed**

```bash
git add frontend
git commit -m "fix: polish frontend run observer"
```

### Task 11: Final Documentation Pass

**Files:**
- Modify: `frontend/README.md`
- Modify: `docs/plans/2026-05-25-runs-frontend-design.md`
- Modify: `docs/plans/2026-05-25-runs-frontend-implementation.md`

**Step 1: Confirm documentation reflects implementation**

Ensure docs mention:

- `DESIGN.md` is mandatory for UI implementation
- `streamdown` renders streamed markdown
- `RunEventStream` uses `StreamMarkdown`
- generic run UI does not expose SOP `env_key`
- SOP page is a thin wrapper over `RunObserver`
- implemented stack is Vite + React 19 + TypeScript + Tailwind CSS v4
- Streamdown is scanned from frontend-local `node_modules`
- app shell and route composition live under `frontend/src/app`
- browser verification evidence is recorded above

**Step 2: Commit documentation updates**

```bash
git add frontend/README.md docs/plans/2026-05-25-runs-frontend-design.md docs/plans/2026-05-25-runs-frontend-implementation.md
git commit -m "docs: finalize runs frontend plan"
```
