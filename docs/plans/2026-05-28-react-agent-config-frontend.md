# ReAct Agent Config Frontend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the smallest useful admin frontend for creating and editing ReAct agent draft configuration.

**Architecture:** Add a new isolated `frontend/src/features/agents` feature that mirrors the existing `llmProviders` structure. Agent pages use the existing workspace shell, existing admin route guard, and existing LLM provider hooks for provider/model dropdown data.

**Tech Stack:** Vite, React 19, TypeScript, React Router, Tailwind CSS v4, Vitest, React Testing Library.

---

## Context

Start from the worktree branch created for this feature:

```bash
cd /Users/wanyaozhong/Projects/change-quality-agent/.worktrees/react-agent-config-frontend-design
```

Read these files before implementation:

- `docs/plans/2026-05-28-react-agent-config-frontend-design.md`
- `frontend/README.md`
- `DESIGN.md`
- `docs/frontend.md`
- `api/openapi.yml`
- `docs/llm-provider-capabilities.md`

Relevant skills for the implementation session:

- @superpowers:executing-plans
- @superpowers:test-driven-development
- @project-structure
- @vercel-react-best-practices

Do not modify `.agents/` or `skills-lock.json`.

---

### Task 1: Agent API Types And Client

**Files:**

- Create: `frontend/src/features/agents/types.ts`
- Create: `frontend/src/features/agents/api.ts`
- Create: `frontend/src/features/agents/api.test.ts`

**Step 1: Write the failing API tests**

Create `frontend/src/features/agents/api.test.ts`:

```ts
// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createAgent,
  getAgent,
  listAgents,
  updateAgentDraft,
} from "./api";
import type { AgentCreate, AgentDetail, AgentDraftUpdate } from "./types";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("agent API", () => {
  it("calls list endpoint with GET", async () => {
    const agents: AgentDetail[] = [];
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(agents));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listAgents()).resolves.toEqual(agents);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/agents",
      expect.objectContaining({ headers: expect.any(Headers) }),
    );
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBeUndefined();
  });

  it("creates a CodeAgent-backed draft", async () => {
    const payload: AgentCreate = {
      description: "Checks release quality.",
      display_name: "Release Reviewer",
      draft: {
        mcp_server_ids: [],
        model: "codeagent:deepseek-v4-pro",
        model_config: {},
        provider_id: null,
        system_prompt: "You are careful.",
        tool_allowlist: [],
      },
    };
    const detail = buildAgent();
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(detail, 201, "Created"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(createAgent(payload)).resolves.toEqual(detail);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/agents",
      expect.objectContaining({
        body: JSON.stringify(payload),
        method: "POST",
      }),
    );
  });

  it("gets and updates an agent draft with encoded id", async () => {
    const detail = buildAgent();
    const update: AgentDraftUpdate = {
      display_name: "Release Reviewer",
      enabled: true,
      draft: {
        mcp_server_ids: [],
        model: "gpt-5-mini",
        model_config: {},
        provider_id: "provider-1",
        system_prompt: "You are careful.",
        tool_allowlist: [],
      },
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(detail))
      .mockResolvedValueOnce(jsonResponse(detail));
    vi.stubGlobal("fetch", fetchMock);

    await getAgent("agent/1");
    await updateAgentDraft("agent/1", update);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/agents/agent%2F1",
      expect.objectContaining({ headers: expect.any(Headers) }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/agents/agent%2F1/draft",
      expect.objectContaining({
        body: JSON.stringify(update),
        method: "PATCH",
      }),
    );
  });
});

function buildAgent(): AgentDetail {
  return {
    created_at: "2026-05-28T00:00:00Z",
    description: "Checks release quality.",
    display_name: "Release Reviewer",
    draft: {
      mcp_server_ids: [],
      model: "codeagent:deepseek-v4-pro",
      model_config: {},
      provider_id: null,
      system_prompt: "You are careful.",
      tool_allowlist: [],
    },
    enabled: true,
    has_draft: true,
    id: "agent-1",
    latest_version: null,
    updated_at: "2026-05-28T00:00:00Z",
  };
}

function jsonResponse(body: unknown, status = 200, statusText = "OK") {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
    statusText,
  });
}
```

**Step 2: Run the failing tests**

Run:

```bash
cd frontend
npm test -- src/features/agents/api.test.ts
```

Expected: FAIL because `./api` and `./types` do not exist.

**Step 3: Add the API types**

Create `frontend/src/features/agents/types.ts`:

```ts
export const CODEAGENT_MODEL_OPTIONS = [
  "codeagent:deepseek-v4-pro",
  "codeagent:codeagent-v4-pro",
] as const;

export type AgentDraftConfig = {
  system_prompt: string;
  model: string;
  provider_id: string | null;
  model_config: Record<string, unknown>;
  tool_allowlist: string[];
  mcp_server_ids: string[];
};

export type AgentVersionSummary = {
  id: string;
  version_number: number;
  model: string;
  provider_id: string | null;
  published_at: string;
};

export type AgentSummary = {
  id: string;
  display_name: string;
  description: string | null;
  enabled: boolean;
  has_draft: boolean;
  latest_version: AgentVersionSummary | null;
  created_at: string;
  updated_at: string;
};

export type AgentDetail = AgentSummary & {
  draft: AgentDraftConfig | null;
};

export type AgentCreate = {
  display_name: string;
  description?: string | null;
  draft: AgentDraftConfig;
};

export type AgentDraftUpdate = {
  display_name?: string | null;
  description?: string | null;
  enabled?: boolean | null;
  draft?: AgentDraftConfig | null;
};
```

**Step 4: Add the API client**

Create `frontend/src/features/agents/api.ts`:

```ts
import { requestJson } from "../../lib/apiClient";
import type {
  AgentCreate,
  AgentDetail,
  AgentDraftUpdate,
  AgentSummary,
} from "./types";

const AGENTS_BASE = "/api/agents";

export function listAgents(): Promise<AgentSummary[]> {
  return requestJson<AgentSummary[]>(AGENTS_BASE);
}

export function getAgent(agentId: string): Promise<AgentDetail> {
  return requestJson<AgentDetail>(buildAgentUrl(agentId));
}

export function createAgent(payload: AgentCreate): Promise<AgentDetail> {
  return requestJson<AgentDetail>(AGENTS_BASE, {
    body: JSON.stringify(payload),
    headers: {
      "Content-Type": "application/json",
    },
    method: "POST",
  });
}

export function updateAgentDraft(
  agentId: string,
  payload: AgentDraftUpdate,
): Promise<AgentDetail> {
  return requestJson<AgentDetail>(`${buildAgentUrl(agentId)}/draft`, {
    body: JSON.stringify(payload),
    headers: {
      "Content-Type": "application/json",
    },
    method: "PATCH",
  });
}

function buildAgentUrl(agentId: string): string {
  return `${AGENTS_BASE}/${encodeURIComponent(agentId)}`;
}
```

**Step 5: Run tests and commit**

Run:

```bash
cd frontend
npm test -- src/features/agents/api.test.ts
```

Expected: PASS.

Commit:

```bash
git add frontend/src/features/agents/types.ts frontend/src/features/agents/api.ts frontend/src/features/agents/api.test.ts
git commit -m "feat: add agent frontend api client"
```

---

### Task 2: Agent Hooks

**Files:**

- Create: `frontend/src/features/agents/hooks.ts`
- Create: `frontend/src/features/agents/hooks.test.tsx`

**Step 1: Write hook tests**

Create `frontend/src/features/agents/hooks.test.tsx` with the same shape as
`frontend/src/features/mcp/hooks.test.tsx`, but mock the new agent API:

```ts
// @vitest-environment jsdom

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createAgent, getAgent, listAgents, updateAgentDraft } from "./api";
import { useAgentDetail, useAgentMutations, useAgents } from "./hooks";
import type { AgentDetail } from "./types";

vi.mock("./api", () => ({
  createAgent: vi.fn(),
  getAgent: vi.fn(),
  listAgents: vi.fn(),
  updateAgentDraft: vi.fn(),
}));

const agent = buildAgent();

beforeEach(() => {
  vi.mocked(listAgents).mockResolvedValue([agent]);
  vi.mocked(getAgent).mockResolvedValue(agent);
  vi.mocked(createAgent).mockResolvedValue(agent);
  vi.mocked(updateAgentDraft).mockResolvedValue(agent);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("agent hooks", () => {
  it("loads agents", async () => {
    const { result } = renderHook(() => useAgents());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toEqual([agent]);
    expect(result.current.error).toBeNull();
  });

  it("loads detail when id is present", async () => {
    const { result } = renderHook(() => useAgentDetail("agent-1"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(getAgent).toHaveBeenCalledWith("agent-1");
    expect(result.current.data).toEqual(agent);
  });

  it("skips detail when id is missing", async () => {
    const { result } = renderHook(() => useAgentDetail(null));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(getAgent).not.toHaveBeenCalled();
    expect(result.current.data).toBeNull();
  });

  it("runs create and update mutations", async () => {
    const { result } = renderHook(() => useAgentMutations());

    await act(async () => {
      await result.current.createAgent({
        display_name: "Release Reviewer",
        draft: agent.draft!,
      });
      await result.current.updateAgentDraft("agent-1", {
        display_name: "Renamed",
      });
    });

    expect(createAgent).toHaveBeenCalled();
    expect(updateAgentDraft).toHaveBeenCalledWith("agent-1", {
      display_name: "Renamed",
    });
  });
});

function buildAgent(): AgentDetail {
  return {
    created_at: "2026-05-28T00:00:00Z",
    description: "Checks release quality.",
    display_name: "Release Reviewer",
    draft: {
      mcp_server_ids: [],
      model: "codeagent:deepseek-v4-pro",
      model_config: {},
      provider_id: null,
      system_prompt: "You are careful.",
      tool_allowlist: [],
    },
    enabled: true,
    has_draft: true,
    id: "agent-1",
    latest_version: null,
    updated_at: "2026-05-28T00:00:00Z",
  };
}
```

**Step 2: Run failing tests**

Run:

```bash
cd frontend
npm test -- src/features/agents/hooks.test.tsx
```

Expected: FAIL because `hooks.ts` does not exist.

**Step 3: Implement hooks**

Create `frontend/src/features/agents/hooks.ts` by adapting
`frontend/src/features/llmProviders/hooks.ts`. Export:

- `useAgents(): AsyncStateWithRefetch<AgentSummary[]>`
- `useAgentDetail(agentId: string | null | undefined)`
- `useAgentMutations()`

Keep the same mounted-ref, request-id, `pendingCount`, and `asError()` pattern.
The mutation object should expose:

```ts
{
  createAgent,
  error,
  pending,
  updateAgentDraft,
}
```

**Step 4: Run tests and commit**

Run:

```bash
cd frontend
npm test -- src/features/agents/hooks.test.tsx
```

Expected: PASS.

Commit:

```bash
git add frontend/src/features/agents/hooks.ts frontend/src/features/agents/hooks.test.tsx
git commit -m "feat: add agent frontend hooks"
```

---

### Task 3: Agent Form

**Files:**

- Create: `frontend/src/features/agents/components/AgentForm.tsx`
- Create: `frontend/src/features/agents/__tests__/AgentForm.test.tsx`

**Step 1: Write form tests**

Create `frontend/src/features/agents/__tests__/AgentForm.test.tsx`:

```tsx
// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AgentForm } from "../components/AgentForm";
import type { AgentDetail } from "../types";
import type { LlmProviderSummary } from "../../llmProviders/types";

const provider = buildProvider({ models: ["gpt-5-mini", "gpt-5"] });

afterEach(() => {
  cleanup();
});

describe("AgentForm", () => {
  it("creates a CodeAgent-backed draft from hard-coded model options", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);

    render(
      <AgentForm
        mode="create"
        agent={null}
        providers={[provider]}
        providersLoading={false}
        pending={false}
        onCancel={vi.fn()}
        onCreate={onCreate}
      />,
    );

    fireEvent.change(screen.getByLabelText("Agent 名称"), {
      target: { value: "Release Reviewer" },
    });
    fireEvent.change(screen.getByLabelText("System Prompt"), {
      target: { value: "You are careful." },
    });
    expect(screen.getByRole("combobox", { name: "CodeAgent 模型" })).toHaveValue(
      "codeagent:deepseek-v4-pro",
    );

    fireEvent.click(screen.getByRole("button", { name: "保存 Agent" }));

    await waitFor(() => expect(onCreate).toHaveBeenCalled());
    expect(onCreate).toHaveBeenCalledWith({
      description: null,
      display_name: "Release Reviewer",
      draft: {
        mcp_server_ids: [],
        model: "codeagent:deepseek-v4-pro",
        model_config: {},
        provider_id: null,
        system_prompt: "You are careful.",
        tool_allowlist: [],
      },
    });
  });

  it("creates a provider-backed draft from provider and model dropdowns", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);

    render(
      <AgentForm
        mode="create"
        agent={null}
        providers={[provider]}
        providersLoading={false}
        pending={false}
        onCancel={vi.fn()}
        onCreate={onCreate}
      />,
    );

    fireEvent.change(screen.getByLabelText("模型来源"), {
      target: { value: "provider" },
    });
    fireEvent.change(screen.getByLabelText("Agent 名称"), {
      target: { value: "Provider Agent" },
    });
    fireEvent.change(screen.getByLabelText("System Prompt"), {
      target: { value: "Use provider." },
    });
    fireEvent.change(screen.getByLabelText("LLM Provider"), {
      target: { value: "provider-1" },
    });
    fireEvent.change(screen.getByLabelText("Provider 模型"), {
      target: { value: "gpt-5" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存 Agent" }));

    await waitFor(() => expect(onCreate).toHaveBeenCalled());
    expect(onCreate.mock.calls[0]?.[0].draft).toMatchObject({
      model: "gpt-5",
      provider_id: "provider-1",
    });
  });

  it("disables saving when selected provider has no models", () => {
    render(
      <AgentForm
        mode="create"
        agent={null}
        providers={[buildProvider({ models: [] })]}
        providersLoading={false}
        pending={false}
        onCancel={vi.fn()}
        onCreate={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("模型来源"), {
      target: { value: "provider" },
    });
    fireEvent.change(screen.getByLabelText("LLM Provider"), {
      target: { value: "provider-1" },
    });

    expect(screen.getByText(/先到 LLM Provider 页面补模型列表/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存 Agent" })).toBeDisabled();
  });

  it("initializes edit form from existing draft", () => {
    render(
      <AgentForm
        mode="edit"
        agent={buildAgent()}
        providers={[provider]}
        providersLoading={false}
        pending={false}
        onCancel={vi.fn()}
        onUpdate={vi.fn()}
      />,
    );

    expect(screen.getByDisplayValue("Release Reviewer")).toBeInTheDocument();
    expect(screen.getByLabelText("模型来源")).toHaveValue("codeagent");
    expect(screen.getByLabelText("启用 Agent")).toBeChecked();
  });
});

function buildProvider(overrides: Partial<LlmProviderSummary> = {}): LlmProviderSummary {
  return {
    api_key_configured: true,
    base_url: null,
    created_at: "2026-05-28T00:00:00Z",
    default_headers: {},
    default_query: {},
    description: null,
    display_name: "OpenAI Main",
    enabled: true,
    id: "provider-1",
    models: ["gpt-5-mini"],
    provider_type: "openai",
    updated_at: "2026-05-28T00:00:00Z",
    ...overrides,
  };
}

function buildAgent(): AgentDetail {
  return {
    created_at: "2026-05-28T00:00:00Z",
    description: "Checks release quality.",
    display_name: "Release Reviewer",
    draft: {
      mcp_server_ids: [],
      model: "codeagent:deepseek-v4-pro",
      model_config: {},
      provider_id: null,
      system_prompt: "You are careful.",
      tool_allowlist: [],
    },
    enabled: true,
    has_draft: true,
    id: "agent-1",
    latest_version: null,
    updated_at: "2026-05-28T00:00:00Z",
  };
}
```

**Step 2: Run failing tests**

Run:

```bash
cd frontend
npm test -- src/features/agents/__tests__/AgentForm.test.tsx
```

Expected: FAIL because `AgentForm` does not exist.

**Step 3: Implement the form**

Create `frontend/src/features/agents/components/AgentForm.tsx`.

Implementation requirements:

- Props:
  - `mode: "create" | "edit"`
  - `agent: AgentDetail | null`
  - `providers: LlmProviderSummary[]`
  - `providersLoading: boolean`
  - `pending?: boolean`
  - `onCancel?: () => void`
  - `onCreate?: (payload: AgentCreate) => Promise<void>`
  - `onUpdate?: (agentId: string, payload: AgentDraftUpdate) => Promise<void>`
- Only use enabled providers for dropdown options.
- Use `CODEAGENT_MODEL_OPTIONS` from `types.ts`.
- In edit mode, infer `modelSource` from `agent.draft.provider_id`.
- Build draft payload with:

```ts
{
  system_prompt: systemPrompt.trim(),
  model: selectedModel,
  provider_id: modelSource === "provider" ? selectedProviderId : null,
  model_config: {},
  tool_allowlist: [],
  mcp_server_ids: [],
}
```

- Use compact design tokens and classes consistent with `LlmProviderForm`.
- Keep cards rounded but do not nest cards inside cards.
- Do not expose advanced fields.

**Step 4: Run tests and commit**

Run:

```bash
cd frontend
npm test -- src/features/agents/__tests__/AgentForm.test.tsx
```

Expected: PASS.

Commit:

```bash
git add frontend/src/features/agents/components/AgentForm.tsx frontend/src/features/agents/__tests__/AgentForm.test.tsx
git commit -m "feat: add agent draft form"
```

---

### Task 4: Agent List Page And Table

**Files:**

- Create: `frontend/src/features/agents/components/AgentTable.tsx`
- Create: `frontend/src/features/agents/pages/AgentPageLayout.tsx`
- Create: `frontend/src/features/agents/pages/AgentListPage.tsx`
- Create: `frontend/src/features/agents/__tests__/AgentPages.test.tsx`

**Step 1: Write list page tests**

Create the first part of `AgentPages.test.tsx`:

```tsx
// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useLlmProviders } from "../../llmProviders/hooks";
import { useAgentDetail, useAgentMutations, useAgents } from "../hooks";
import { AgentListPage } from "../pages/AgentListPage";
import type { AgentDetail } from "../types";

vi.mock("../hooks", () => ({
  useAgentDetail: vi.fn(),
  useAgentMutations: vi.fn(),
  useAgents: vi.fn(),
}));

vi.mock("../../llmProviders/hooks", () => ({
  useLlmProviders: vi.fn(),
}));

const agent = buildAgent();
const refetchAgents = vi.fn();

beforeEach(() => {
  refetchAgents.mockReset();
  vi.mocked(useAgents).mockReturnValue({
    data: [agent],
    error: null,
    loading: false,
    refetch: refetchAgents,
  });
  vi.mocked(useAgentDetail).mockReturnValue({
    data: agent,
    error: null,
    loading: false,
    refetch: vi.fn(),
  });
  vi.mocked(useAgentMutations).mockReturnValue({
    createAgent: vi.fn(),
    error: null,
    pending: false,
    updateAgentDraft: vi.fn(),
  });
  vi.mocked(useLlmProviders).mockReturnValue({
    data: [
      {
        api_key_configured: true,
        base_url: null,
        created_at: "2026-05-28T00:00:00Z",
        default_headers: {},
        default_query: {},
        description: null,
        display_name: "OpenAI Main",
        enabled: true,
        id: "provider-1",
        models: ["gpt-5-mini"],
        provider_type: "openai",
        updated_at: "2026-05-28T00:00:00Z",
      },
    ],
    error: null,
    loading: false,
    refetch: vi.fn(),
  });
});

afterEach(() => {
  cleanup();
});

describe("agent pages", () => {
  it("renders list rows, filters by search, and navigates to create", () => {
    render(
      <MemoryRouter initialEntries={["/agents"]}>
        <Routes>
          <Route element={<AgentListPage />} path="/agents" />
          <Route element={<div>新增 Agent 页面</div>} path="/agents/new" />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole("main", { name: "Agent 配置主内容" })).toBeInTheDocument();
    expect(screen.getByText("Release Reviewer")).toBeInTheDocument();
    expect(screen.getByText("codeagent:deepseek-v4-pro")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("搜索 Agent"), {
      target: { value: "missing" },
    });
    expect(screen.getByText("暂无 Agent。")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "新增 Agent" }));
    expect(screen.getByText("新增 Agent 页面")).toBeInTheDocument();
  });
});

function buildAgent(): AgentDetail {
  return {
    created_at: "2026-05-28T00:00:00Z",
    description: "Checks release quality.",
    display_name: "Release Reviewer",
    draft: {
      mcp_server_ids: [],
      model: "codeagent:deepseek-v4-pro",
      model_config: {},
      provider_id: null,
      system_prompt: "You are careful.",
      tool_allowlist: [],
    },
    enabled: true,
    has_draft: true,
    id: "agent-1",
    latest_version: null,
    updated_at: "2026-05-28T00:00:00Z",
  };
}
```

**Step 2: Run failing tests**

Run:

```bash
cd frontend
npm test -- src/features/agents/__tests__/AgentPages.test.tsx
```

Expected: FAIL because pages do not exist.

**Step 3: Implement list UI**

Create `AgentPageLayout.tsx` by adapting `LlmProviderPageLayout.tsx`:

- `aria-label="Agent 配置主内容"`
- same breadcrumb/header/body layout
- title and actions props

Create `AgentTable.tsx` by adapting `LlmProviderTable.tsx`:

- Props include `agents`, `providers`, `loading`, `error`, `searchText`,
  `onSearchTextChange`, `onRefresh`, `onCreateAgent`.
- Table min width around `900px`.
- Columns: Agent, 状态, 模型, Provider, Draft, 更新时间, 操作.
- The edit action is a `Link` to `/agents/${agent.id}/edit`.

Create `AgentListPage.tsx`:

- Call `useAgents()` and `useLlmProviders()`.
- Filter by id, display name, description, draft model, latest version model.
- Render `AgentPageLayout` and `AgentTable`.
- Navigate create button to `/agents/new`.

**Step 4: Run tests and commit**

Run:

```bash
cd frontend
npm test -- src/features/agents/__tests__/AgentPages.test.tsx
```

Expected: PASS.

Commit:

```bash
git add frontend/src/features/agents/components/AgentTable.tsx frontend/src/features/agents/pages/AgentPageLayout.tsx frontend/src/features/agents/pages/AgentListPage.tsx frontend/src/features/agents/__tests__/AgentPages.test.tsx
git commit -m "feat: add agent list page"
```

---

### Task 5: Agent Create And Edit Pages

**Files:**

- Create: `frontend/src/features/agents/pages/AgentFormPage.tsx`
- Modify: `frontend/src/features/agents/__tests__/AgentPages.test.tsx`

**Step 1: Add create/edit page tests**

Extend `AgentPages.test.tsx` with:

```tsx
import { waitFor } from "@testing-library/react";
import { AgentCreatePage, AgentEditPage } from "../pages/AgentFormPage";

const createAgent = vi.fn();
const updateAgentDraft = vi.fn();

beforeEach(() => {
  createAgent.mockReset();
  updateAgentDraft.mockReset();
  createAgent.mockResolvedValue(agent);
  updateAgentDraft.mockResolvedValue(agent);
  vi.mocked(useAgentMutations).mockReturnValue({
    createAgent,
    error: null,
    pending: false,
    updateAgentDraft,
  });
});

it("creates an agent and returns to the list", async () => {
  render(
    <MemoryRouter initialEntries={["/agents/new"]}>
      <Routes>
        <Route element={<AgentCreatePage />} path="/agents/new" />
        <Route element={<div>Agent 列表</div>} path="/agents" />
      </Routes>
    </MemoryRouter>,
  );

  fireEvent.change(screen.getByLabelText("Agent 名称"), {
    target: { value: "Release Reviewer" },
  });
  fireEvent.change(screen.getByLabelText("System Prompt"), {
    target: { value: "You are careful." },
  });
  fireEvent.click(screen.getByRole("button", { name: "保存 Agent" }));

  await waitFor(() => expect(createAgent).toHaveBeenCalled());
  expect(screen.getByText("Agent 列表")).toBeInTheDocument();
});

it("edits an existing agent and returns to the list", async () => {
  render(
    <MemoryRouter initialEntries={["/agents/agent-1/edit"]}>
      <Routes>
        <Route element={<AgentEditPage />} path="/agents/:agentId/edit" />
        <Route element={<div>Agent 列表</div>} path="/agents" />
      </Routes>
    </MemoryRouter>,
  );

  fireEvent.change(screen.getByLabelText("Agent 名称"), {
    target: { value: "Release Reviewer Updated" },
  });
  fireEvent.click(screen.getByRole("button", { name: "保存 Agent" }));

  await waitFor(() => expect(updateAgentDraft).toHaveBeenCalledWith(
    "agent-1",
    expect.objectContaining({ display_name: "Release Reviewer Updated" }),
  ));
  expect(screen.getByText("Agent 列表")).toBeInTheDocument();
});
```

If import placement becomes awkward, rewrite the test file cleanly instead of
patching it piecemeal.

**Step 2: Run failing tests**

Run:

```bash
cd frontend
npm test -- src/features/agents/__tests__/AgentPages.test.tsx
```

Expected: FAIL because `AgentFormPage.tsx` does not exist.

**Step 3: Implement form pages**

Create `AgentFormPage.tsx`:

- `AgentCreatePage`:
  - calls `useLlmProviders()`
  - calls `useAgentMutations()`
  - renders `AgentPageLayout`
  - on create success navigates to `/agents` with route state
    `{ agentNotice: "Agent 已创建。" }`
- `AgentEditPage`:
  - reads `agentId` from `useParams`
  - calls `useAgentDetail(agentId)`
  - calls `useLlmProviders()`
  - renders loading/error states
  - on update success navigates to `/agents` with route state
    `{ agentNotice: "Agent 已保存。" }`

Keep aside content simple: a compact note explaining that publish/test-run are
not part of this page yet.

**Step 4: Run tests and commit**

Run:

```bash
cd frontend
npm test -- src/features/agents/__tests__/AgentPages.test.tsx
```

Expected: PASS.

Commit:

```bash
git add frontend/src/features/agents/pages/AgentFormPage.tsx frontend/src/features/agents/__tests__/AgentPages.test.tsx
git commit -m "feat: add agent create and edit pages"
```

---

### Task 6: App Routing And Sidebar

**Files:**

- Modify: `frontend/src/app/App.tsx`
- Modify: `frontend/src/app/routing/workspaceRoutes.ts`
- Modify: `frontend/src/app/WorkspaceSidebar.tsx`
- Modify: `frontend/src/app/WorkspaceSidebar.test.tsx`
- Modify: `frontend/src/app/routing/ProtectedRoute.test.tsx`

**Step 1: Update route/sidebar tests first**

In `WorkspaceSidebar.test.tsx`:

- Expect `Agent 配置` in expanded and collapsed nav.
- Expect order: SOP, MCP, LLM Provider, Agent.
- Add click test expecting `onNavigate("agents")`.

In `ProtectedRoute.test.tsx`:

- Mock `../../features/agents/pages/AgentListPage`.
- Mock `../../features/agents/pages/AgentFormPage`.
- Add non-admin `/agents` blocked test.
- Add admin `/agents` allowed test.

Run:

```bash
cd frontend
npm test -- src/app/WorkspaceSidebar.test.tsx src/app/routing/ProtectedRoute.test.tsx
```

Expected: FAIL because app routing does not know `agents`.

**Step 2: Implement route definitions**

Modify `workspaceRoutes.ts`:

- Change `WorkspaceRouteKey` to include `"agents"`.
- Add:

```ts
agents: {
  key: "agents",
  label: "Agent 配置",
  path: "/agents",
  requiresAdmin: true,
  showInSidebar: true,
}
```

- Append `workspaceRoutes.agents` to `workspaceSidebarRoutes`.
- Update `getWorkspaceRouteKey()` to check `/agents` after
  `/llm-providers` and before `/mcp` fallback.

Modify `WorkspaceSidebar.tsx`:

- Add a distinct icon branch for `agents`. Prefer an existing inline icon
  style already used in the file if lucide is not installed.

Modify `App.tsx`:

- Import `AgentListPage`, `AgentCreatePage`, `AgentEditPage`.
- Add protected routes:

```tsx
<Route element={<ProtectedRoute route={workspaceRoutes.agents} />}>
  <Route element={<AgentListPage />} path="agents" />
  <Route element={<AgentCreatePage />} path="agents/new" />
  <Route element={<AgentEditPage />} path="agents/:agentId/edit" />
</Route>
```

**Step 3: Run tests and commit**

Run:

```bash
cd frontend
npm test -- src/app/WorkspaceSidebar.test.tsx src/app/routing/ProtectedRoute.test.tsx
```

Expected: PASS.

Commit:

```bash
git add frontend/src/app/App.tsx frontend/src/app/routing/workspaceRoutes.ts frontend/src/app/WorkspaceSidebar.tsx frontend/src/app/WorkspaceSidebar.test.tsx frontend/src/app/routing/ProtectedRoute.test.tsx
git commit -m "feat: route agent config pages"
```

---

### Task 7: Full Verification

**Files:**

- Modify only if verification exposes issues.

**Step 1: Run focused frontend tests**

Run:

```bash
cd frontend
npm test -- src/features/agents src/app/WorkspaceSidebar.test.tsx src/app/routing/ProtectedRoute.test.tsx
```

Expected: all selected test files PASS.

**Step 2: Run full frontend test suite**

Run:

```bash
cd frontend
npm test
```

Expected: all frontend tests PASS.

**Step 3: Run production build**

Run:

```bash
cd frontend
npm run build
```

Expected: TypeScript build and Vite build PASS.

**Step 4: Optional backend contract safety check**

Run only if API payload types or OpenAPI assumptions changed during
implementation:

```bash
make test
```

Expected: backend tests PASS or DB-marked tests SKIP when local DB is absent.

**Step 5: Final commit if needed**

If verification required any fixes:

```bash
git add frontend
git commit -m "test: verify agent config frontend"
```

If there were no fixes, do not create an empty commit.

**Step 6: Report**

Summarize:

- Files added/modified.
- Tests run and exact pass/fail result.
- Any known non-goals still intentionally absent: detail, publish, delete, test-run UI.
