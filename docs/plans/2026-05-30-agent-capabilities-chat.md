# Agent Capabilities Chat Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let admins configure Agent draft built-in tools and MCP servers, save the draft, and immediately run a real multi-turn chat against that draft.

**Architecture:** Add a backend capability registry and Agent session service under the existing FastAPI/service/repository boundaries. Reuse `AgentRuntime`, `sessions/messages`, `SessionBroadcast`, and `useSessionStream` instead of creating a new transcript model. Keep draft chat separate from publish/version flows.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy async repositories, LangChain `create_agent`, React 19, React Router, TypeScript, Vite, Tailwind CSS v4, Vitest, pytest.

---

## Constraints

- Work only inside the worktree `/Users/wanyaozhong/Projects/change-quality-agent/.worktrees/agent-capabilities-chat`.
- Do not edit the main checkout at `/Users/wanyaozhong/Projects/change-quality-agent`.
- Do not commit `.agents/` or `skills-lock.json`.
- Follow `DESIGN.md` for frontend UI.
- Keep Python files under 1000 lines.
- Use `Annotated` dependencies and route parameters in FastAPI.

## Task 1: Backend capability schemas and registry

**Files:**

- Modify: `app/schemas/agents.py`
- Create: `app/services/agent_capabilities.py`
- Test: `tests/test_agent_capabilities.py`

**Step 1: Write the failing tests**

Create `tests/test_agent_capabilities.py`:

```python
from uuid import uuid4

import pytest

from app.services.agent_capabilities import (
    BUILTIN_AGENT_TOOLS,
    AgentCapabilityService,
    UnknownBuiltinToolError,
)


class FakeMcpServer:
    def __init__(self, *, server_id, name="Docs MCP", enabled=True, status="running", tools=None):
        self.id = server_id
        self.name = name
        self.enabled = enabled
        self.runtime_status = status
        self.tools = tools or [object(), object()]


class FakeMcpRepository:
    def __init__(self, servers):
        self._servers = servers

    async def list_servers(self):
        return list(self._servers)


@pytest.mark.asyncio
async def test_capability_service_lists_builtin_tools_and_mcp_servers():
    server_id = uuid4()
    service = AgentCapabilityService(
        mcp_repository=FakeMcpRepository([
            FakeMcpServer(server_id=server_id, tools=[object()]),
        ]),
    )

    result = await service.list_capabilities()

    assert result.builtin_tools
    assert result.builtin_tools[0].name == BUILTIN_AGENT_TOOLS[0].name
    assert result.mcp_servers[0].id == str(server_id)
    assert result.mcp_servers[0].tool_count == 1


def test_capability_service_rejects_unknown_builtin_tool():
    service = AgentCapabilityService(mcp_repository=FakeMcpRepository([]))

    with pytest.raises(UnknownBuiltinToolError):
        service.resolve_builtin_tools(["missing-tool"])
```

**Step 2: Run the failing test**

Run:

```bash
pytest tests/test_agent_capabilities.py -v
```

Expected: FAIL because `app.services.agent_capabilities` does not exist.

**Step 3: Add schemas**

In `app/schemas/agents.py`, add:

```python
class BuiltinAgentToolCapability(BaseModel):
    name: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str | None = None
    enabled: bool = True


class McpAgentCapability(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    enabled: bool
    runtime_status: str
    tool_count: int = Field(ge=0)


class AgentCapabilities(BaseModel):
    builtin_tools: list[BuiltinAgentToolCapability] = Field(default_factory=list)
    mcp_servers: list[McpAgentCapability] = Field(default_factory=list)
```

**Step 4: Add service**

Create `app/services/agent_capabilities.py`:

```python
from dataclasses import dataclass
from typing import Protocol

from langchain_core.tools import tool

from app.schemas.agents import (
    AgentCapabilities,
    BuiltinAgentToolCapability,
    McpAgentCapability,
)


class UnknownBuiltinToolError(ValueError):
    pass


@dataclass(frozen=True)
class BuiltinAgentTool:
    name: str
    label: str
    description: str | None
    enabled: bool = True
    implementation: object | None = None


@tool("echo")
def echo_tool(text: str) -> str:
    """Echo text back to the caller for local Agent testing."""
    return text


BUILTIN_AGENT_TOOLS: tuple[BuiltinAgentTool, ...] = (
    BuiltinAgentTool(
        name="echo",
        label="Echo",
        description="Echoes input text. Useful for validating Agent tool wiring.",
        implementation=echo_tool,
    ),
)


class McpRepositoryLike(Protocol):
    async def list_servers(self) -> list[object]:
        ...


class AgentCapabilityService:
    def __init__(self, *, mcp_repository: McpRepositoryLike) -> None:
        self._mcp_repository = mcp_repository

    async def list_capabilities(self) -> AgentCapabilities:
        servers = await self._mcp_repository.list_servers()
        return AgentCapabilities(
            builtin_tools=[
                BuiltinAgentToolCapability(
                    name=item.name,
                    label=item.label,
                    description=item.description,
                    enabled=item.enabled,
                )
                for item in BUILTIN_AGENT_TOOLS
            ],
            mcp_servers=[
                McpAgentCapability(
                    id=str(server.id),
                    name=server.name,
                    enabled=bool(server.enabled),
                    runtime_status=str(server.runtime_status),
                    tool_count=len(getattr(server, "tools", []) or []),
                )
                for server in servers
            ],
        )

    def resolve_builtin_tools(self, names: list[str]) -> list[object]:
        registry = {item.name: item for item in BUILTIN_AGENT_TOOLS if item.enabled}
        tools: list[object] = []
        for name in names:
            item = registry.get(name)
            if item is None or item.implementation is None:
                raise UnknownBuiltinToolError(name)
            tools.append(item.implementation)
        return tools
```

**Step 5: Run the test**

Run:

```bash
pytest tests/test_agent_capabilities.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add app/schemas/agents.py app/services/agent_capabilities.py tests/test_agent_capabilities.py
git commit -m "feat: add agent capability registry"
```

## Task 2: Backend capabilities endpoint

**Files:**

- Modify: `app/api/deps.py`
- Modify: `app/api/v1/agents.py`
- Test: `tests/test_agents_api.py`

**Step 1: Write failing API test**

Append to `tests/test_agents_api.py`:

```python
class FakeCapabilityService:
    async def list_capabilities(self):
        from app.schemas.agents import AgentCapabilities, BuiltinAgentToolCapability, McpAgentCapability

        return AgentCapabilities(
            builtin_tools=[
                BuiltinAgentToolCapability(
                    name="echo",
                    label="Echo",
                    description="Echoes input.",
                    enabled=True,
                )
            ],
            mcp_servers=[
                McpAgentCapability(
                    id="mcp-1",
                    name="Docs MCP",
                    enabled=True,
                    runtime_status="running",
                    tool_count=2,
                )
            ],
        )


@pytest.mark.asyncio
async def test_get_agent_capabilities_returns_builtin_tools_and_mcp_servers():
    get_agent_capability_service = getattr(deps, "get_agent_capability_service")
    app.dependency_overrides[get_agent_capability_service] = lambda: FakeCapabilityService()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/agents/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["builtin_tools"][0]["name"] == "echo"
    assert body["mcp_servers"][0]["tool_count"] == 2
```

**Step 2: Run failing test**

Run:

```bash
pytest tests/test_agents_api.py::test_get_agent_capabilities_returns_builtin_tools_and_mcp_servers -v
```

Expected: FAIL because dependency/route does not exist.

**Step 3: Add dependency**

In `app/api/deps.py`, import `AgentCapabilityService` and add:

```python
def get_agent_capability_service(
    mcp_repository: McpRepositoryDep,
) -> AgentCapabilityService:
    return AgentCapabilityService(mcp_repository=mcp_repository)


AgentCapabilityServiceDep = Annotated[
    AgentCapabilityService,
    Depends(get_agent_capability_service),
]
```

**Step 4: Add route before `/{agent_id}`**

In `app/api/v1/agents.py`, import `AgentCapabilityServiceDep` and `AgentCapabilities`, then add before `@router.get("/{agent_id}")`:

```python
@router.get("/capabilities")
async def get_agent_capabilities(
    service: AgentCapabilityServiceDep,
) -> AgentCapabilities:
    return await service.list_capabilities()
```

**Step 5: Run test**

Run:

```bash
pytest tests/test_agents_api.py::test_get_agent_capabilities_returns_builtin_tools_and_mcp_servers -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add app/api/deps.py app/api/v1/agents.py tests/test_agents_api.py
git commit -m "feat: expose agent capabilities API"
```

## Task 3: Backend Agent draft session service

**Files:**

- Modify: `app/schemas/agents.py`
- Modify: `app/services/agents.py`
- Modify: `app/api/deps.py`
- Modify: `app/api/v1/agents.py`
- Test: `tests/test_agent_service.py`
- Test: `tests/test_agents_api.py`

**Step 1: Add failing service tests**

In `tests/test_agent_service.py`, add tests for creating a draft chat session and rejecting disabled agents. Use existing fake repository style in that file. The test should assert:

```python
result = await service.start_draft_session(agent.id, AgentSessionStart(message="你好"))
assert result.session_id == 123
assert result.stream_url == "/api/sessions/123/stream?after=0"
```

Also assert disabled Agent raises `AgentDisabledError`.

**Step 2: Run failing tests**

Run:

```bash
pytest tests/test_agent_service.py -v
```

Expected: FAIL because request/response schemas and service method do not exist.

**Step 3: Add request/response schemas**

In `app/schemas/agents.py`, add:

```python
class AgentSessionStart(BaseModel):
    message: str = Field(min_length=1)
    session_id: int | None = Field(default=None, ge=1)


class AgentSessionStartResponse(BaseModel):
    session_id: int
    stream_url: str
```

**Step 4: Add draft runtime value object**

In `app/services/agents.py`, add an internal class compatible with `AgentRuntime`:

```python
class DraftAgentRuntimeConfig:
    def __init__(self, draft: AgentDraftConfig) -> None:
        self.model = draft.model
        self.system_prompt = draft.system_prompt
        self.provider_id = draft.provider_id
        self.model_config = draft.model_parameters
        self.tool_allowlist = list(draft.tool_allowlist)
        self.mcp_server_ids = list(draft.mcp_server_ids)
```

**Step 5: Add service dependencies and method**

Extend `AgentService.__init__` to accept optional:

```python
session_repository: SessionRepository | None = None
session_broadcast: SessionBroadcast | None = None
runtime: AgentRuntime | None = None
schedule_agent_run: Callable[[int, UUID], object] | None = None
```

Add `start_draft_session(...)` that:

- loads agent with `_require_agent`
- validates `agent.enabled`
- validates `agent.draft_config`
- creates or loads a session
- writes metadata tying session to the agent via message `additional_kwargs`, at minimum `{ "agent_id": str(agent_id) }`
- appends the user message with `role="user"`
- commits
- schedules background run callback if configured
- returns `AgentSessionStartResponse(session_id=session.id, stream_url=f"/api/sessions/{session.id}/stream?after=0")`

If `session_id` is present, list existing messages and verify at least one message has matching `additional_kwargs.agent_id`; otherwise raise `AgentNotFoundError` or a new `AgentSessionNotFoundError` mapped to 404.

**Step 6: Add route and dependency wiring**

In `app/api/deps.py`, update `get_agent_service` to inject `SessionRepositoryDep` and `SessionBroadcastDep`. If a background runner is needed, create a separate dependency that can add a `BackgroundTasks` task from the route instead of hiding FastAPI objects in the service.

In `app/api/v1/agents.py`, add:

```python
@router.post("/{agent_id}/sessions")
async def start_agent_session(
    agent_id: Annotated[UUID, Path()],
    request: AgentSessionStart,
    service: AgentServiceDep,
) -> AgentSessionStartResponse:
    try:
        return await service.start_draft_session(agent_id, request)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    except AgentDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST) from exc
    except AgentDraftInvalidError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST) from exc
```

**Step 7: Add API tests**

In `tests/test_agents_api.py`, add:

```python
@pytest.mark.asyncio
async def test_start_agent_session_returns_session_id_and_stream_url():
    # override AgentServiceDep or repository/session dependencies
    # POST /api/agents/{agent.id}/sessions with {"message": "你好"}
    # assert status 200 and stream_url
```

**Step 8: Run tests**

Run:

```bash
pytest tests/test_agent_service.py tests/test_agents_api.py -v
```

Expected: PASS.

**Step 9: Commit**

```bash
git add app/schemas/agents.py app/services/agents.py app/api/deps.py app/api/v1/agents.py tests/test_agent_service.py tests/test_agents_api.py
git commit -m "feat: start agent draft chat sessions"
```

## Task 4: Backend Agent run execution and tool resolver

**Files:**

- Create: `app/services/agent_runs.py`
- Modify: `app/core/agent_runtime.py`
- Modify: `app/api/deps.py`
- Test: `tests/test_agent_runtime.py`
- Test: `tests/test_agent_runs.py`

**Step 1: Write failing runtime resolver test**

In `tests/test_agent_runtime.py`, add a test that uses a resolver returning built-in tools and asserts unknown built-in tool raises from `_build_agent`.

**Step 2: Add concrete resolver**

In `app/core/agent_runtime.py`, replace `StaticToolResolver` or add a new resolver class that composes:

- `AgentCapabilityService.resolve_builtin_tools(tool_allowlist)`
- MCP tool resolution placeholder for selected MCP servers

For the first implementation, MCP runtime binding can return no concrete tools if the current MCP client-to-LangChain adapter is not present, but validation must reject missing/disabled/no-tool servers in the Agent run service before runtime invocation. Keep this explicit; do not silently claim MCP tools were attached if they were not.

**Step 3: Write failing run service test**

Create `tests/test_agent_runs.py` with fakes for repository, session repository, broadcast, and runtime. Assert:

- user message history is passed to runtime
- assistant result messages are persisted
- session status becomes `completed`
- runtime exception sets session status `failed` and publishes failed event

**Step 4: Implement run service**

Create `app/services/agent_runs.py`:

```python
class AgentRunService:
    def __init__(
        self,
        *,
        agent_repository: AgentRepository,
        session_repository: SessionRepository,
        session_broadcast: SessionBroadcast,
        runtime: AgentRuntime,
        commit: Callable[[], object],
    ) -> None: ...

    async def run_draft_turn(self, *, agent_id: UUID, session_id: int) -> None:
        # load agent and draft
        # load messages from session
        # convert messages to LangChain-compatible JSON role/content items
        # await runtime.run(version=DraftAgentRuntimeConfig(draft), messages=history)
        # persist assistant/tool messages
        # set completed or failed
        # publish persisted message events and terminal event
```

Do not put this orchestration in the route file.

**Step 5: Add background scheduling**

In `app/api/v1/agents.py`, use `BackgroundTasks` in `start_agent_session` and schedule `AgentRunService.run_draft_turn`. Keep route thin: call service to create session and then add background task.

If dependency injection becomes awkward, add `AgentRunServiceDep` in `app/api/deps.py`.

**Step 6: Run tests**

Run:

```bash
pytest tests/test_agent_runtime.py tests/test_agent_runs.py tests/test_agents_api.py -v
```

Expected: PASS.

**Step 7: Commit**

```bash
git add app/core/agent_runtime.py app/services/agent_runs.py app/api/deps.py app/api/v1/agents.py tests/test_agent_runtime.py tests/test_agent_runs.py tests/test_agents_api.py
git commit -m "feat: run agent draft chat turns"
```

## Task 5: Frontend API types and hooks

**Files:**

- Modify: `frontend/src/features/agents/types.ts`
- Modify: `frontend/src/features/agents/api.ts`
- Modify: `frontend/src/features/agents/hooks.ts`
- Test: `frontend/src/features/agents/api.test.ts`
- Test: `frontend/src/features/agents/hooks.test.tsx`

**Step 1: Write failing API tests**

In `frontend/src/features/agents/api.test.ts`, add tests for:

```ts
await getAgentCapabilities();
expect(fetch).toHaveBeenCalledWith("/api/agents/capabilities", expect.any(Object));

await startAgentSession("agent-1", { message: "你好", session_id: 7 });
expect(fetch).toHaveBeenCalledWith("/api/agents/agent-1/sessions", expect.objectContaining({ method: "POST" }));
```

**Step 2: Add types**

In `frontend/src/features/agents/types.ts`, add:

```ts
export type BuiltinAgentToolCapability = {
  name: string;
  label: string;
  description: string | null;
  enabled: boolean;
};

export type McpAgentCapability = {
  id: string;
  name: string;
  enabled: boolean;
  runtime_status: string;
  tool_count: number;
};

export type AgentCapabilities = {
  builtin_tools: BuiltinAgentToolCapability[];
  mcp_servers: McpAgentCapability[];
};

export type AgentSessionStart = {
  message: string;
  session_id?: number | null;
};

export type AgentSessionStartResponse = {
  session_id: number;
  stream_url: string;
};
```

**Step 3: Add API functions**

In `frontend/src/features/agents/api.ts`, add:

```ts
export function getAgentCapabilities(): Promise<AgentCapabilities> {
  return requestJson<AgentCapabilities>(`${AGENTS_BASE}/capabilities`);
}

export function startAgentSession(
  agentId: string,
  payload: AgentSessionStart,
): Promise<AgentSessionStartResponse> {
  return requestJson<AgentSessionStartResponse>(`${buildAgentUrl(agentId)}/sessions`, {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
}
```

**Step 4: Add hooks**

In `frontend/src/features/agents/hooks.ts`, add `useAgentCapabilities` and `useAgentChatMutations` following existing mounted/request-id patterns.

**Step 5: Run frontend tests**

Run:

```bash
cd frontend && npm test -- --run src/features/agents/api.test.ts src/features/agents/hooks.test.tsx
```

Expected: PASS.

**Step 6: Commit**

```bash
git add frontend/src/features/agents/types.ts frontend/src/features/agents/api.ts frontend/src/features/agents/hooks.ts frontend/src/features/agents/api.test.ts frontend/src/features/agents/hooks.test.tsx
git commit -m "feat: add frontend agent chat APIs"
```

## Task 6: Frontend Agent form capability selection

**Files:**

- Modify: `frontend/src/features/agents/components/AgentForm.tsx`
- Modify: `frontend/src/features/agents/pages/AgentFormPage.tsx`
- Test: `frontend/src/features/agents/__tests__/AgentForm.test.tsx`
- Test: `frontend/src/features/agents/__tests__/AgentPages.test.tsx`

**Step 1: Write failing form tests**

Update `AgentForm.test.tsx` so `AgentForm` receives a `capabilities` prop. Add tests that:

- select built-in tool `echo`
- select MCP server `mcp-1`
- submit create
- expect payload draft contains `tool_allowlist: ["echo"]` and `mcp_server_ids: ["mcp-1"]`

Also add edit test where draft references missing tool/server and save is disabled.

**Step 2: Extend AgentForm props and state**

In `AgentForm.tsx`, add props:

```ts
capabilities: AgentCapabilities;
capabilitiesLoading: boolean;
```

Add state:

```ts
const [selectedToolNames, setSelectedToolNames] = useState<string[]>([]);
const [selectedMcpServerIds, setSelectedMcpServerIds] = useState<string[]>([]);
```

Initialize from `agent.draft?.tool_allowlist` and `agent.draft?.mcp_server_ids` in the existing edit/create effect.

**Step 3: Render capability cards**

Add section between model controls and system prompt:

```tsx
<section className="rounded-2xl border border-hairline-soft bg-canvas-soft/50 p-3">
  <h2 className="text-sm font-semibold text-ink">能力</h2>
  {/* built-in tools cards */}
  {/* MCP server cards */}
</section>
```

Use checkbox cards with cobalt selected border. Show missing selections as unavailable warnings and include them in `saveBlocked`.

**Step 4: Include capabilities in payload**

Change `buildAgentDraftPayload` signature to accept selected tools and MCP ids, and return trimmed arrays instead of `[]`.

**Step 5: Wire page hook**

In `AgentFormPage.tsx`, call `useAgentCapabilities()` and pass result into `AgentForm`.

On create success:

```ts
const created = await mutations.createAgent(payload);
navigate(`/agents/${created.id}/chat`, { state: { agentNotice: "Agent 已创建。" } });
```

On edit success:

```ts
const updated = await mutations.updateAgentDraft(id, payload);
navigate(`/agents/${updated.id}/chat`, { state: { agentNotice: "Agent 已保存。" } });
```

**Step 6: Run frontend form/page tests**

Run:

```bash
cd frontend && npm test -- --run src/features/agents/__tests__/AgentForm.test.tsx src/features/agents/__tests__/AgentPages.test.tsx
```

Expected: PASS.

**Step 7: Commit**

```bash
git add frontend/src/features/agents/components/AgentForm.tsx frontend/src/features/agents/pages/AgentFormPage.tsx frontend/src/features/agents/__tests__/AgentForm.test.tsx frontend/src/features/agents/__tests__/AgentPages.test.tsx
git commit -m "feat: configure agent capabilities in form"
```

## Task 7: Frontend Agent chat page

**Files:**

- Create: `frontend/src/features/agents/pages/AgentChatPage.tsx`
- Modify: `frontend/src/app/App.tsx`
- Modify: `frontend/src/features/agents/components/AgentTable.tsx`
- Test: `frontend/src/features/agents/__tests__/AgentChatPage.test.tsx`
- Test: `frontend/src/features/agents/__tests__/AgentPages.test.tsx`

**Step 1: Write failing page test**

Create `AgentChatPage.test.tsx` with mocks for `useAgentDetail`, `useAgentChatMutations`, and `useSessionStream`. Assert:

- page renders Agent name and empty state
- typing a message and clicking send calls `startAgentSession(agentId, { message, session_id: null })`
- after response `{ session_id: 42 }`, `useSessionStream(42)` is used on next render
- send button is disabled while mutation is pending or connection is open

**Step 2: Implement AgentChatPage**

Create page with:

- route param `agentId`
- `useAgentDetail(agentId)` for header metadata
- local `sessionId` state
- `useSessionStream(sessionId)` for transcript
- composer state
- `handleSend` that calls start session with current `sessionId`

Message rendering rules:

```tsx
function MessageBubble({ message }: { message: SessionMessage }) {
  if (message.role === "assistant") return <StreamMarkdown>{message.content}</StreamMarkdown>;
  if (message.role === "tool") return <details>...</details>;
  return <p>{message.content}</p>;
}
```

For live buffers, render values from `state.liveBuffers` as temporary assistant output.

**Step 3: Add route**

In `frontend/src/app/App.tsx`, import `AgentChatPage` and add under protected agents routes:

```tsx
<Route element={<AgentChatPage />} path="agents/:agentId/chat" />
```

**Step 4: Add list action**

In `AgentTable.tsx`, add a second action link:

```tsx
<Link to={`/agents/${agent.id}/chat`}>对话</Link>
```

Keep edit action available.

**Step 5: Run tests**

Run:

```bash
cd frontend && npm test -- --run src/features/agents/__tests__/AgentChatPage.test.tsx src/features/agents/__tests__/AgentPages.test.tsx
```

Expected: PASS.

**Step 6: Commit**

```bash
git add frontend/src/features/agents/pages/AgentChatPage.tsx frontend/src/app/App.tsx frontend/src/features/agents/components/AgentTable.tsx frontend/src/features/agents/__tests__/AgentChatPage.test.tsx frontend/src/features/agents/__tests__/AgentPages.test.tsx
git commit -m "feat: add agent chat page"
```

## Task 8: OpenAPI and documentation

**Files:**

- Modify: `api/openapi.yml`
- Modify: `docs/frontend.md`
- Test: `tests/test_openapi_contract.py`

**Step 1: Update OpenAPI**

Add paths:

- `GET /api/agents/capabilities`
- `POST /api/agents/{agent_id}/sessions`

Add schemas:

- `BuiltinAgentToolCapability`
- `McpAgentCapability`
- `AgentCapabilities`
- `AgentSessionStart`
- `AgentSessionStartResponse`

**Step 2: Update frontend docs**

In `docs/frontend.md`, update the Agent section:

- add `/agents/:agentId/chat`
- document capability section in `AgentForm`
- document save redirect to chat
- document chat page uses generic sessions stream

**Step 3: Run contract test**

Run:

```bash
pytest tests/test_openapi_contract.py -v
```

Expected: PASS.

**Step 4: Commit**

```bash
git add api/openapi.yml docs/frontend.md tests/test_openapi_contract.py
git commit -m "docs: document agent capabilities chat contract"
```

## Task 9: Focused final verification

**Files:**

- No source edits expected unless a focused verification failure identifies a defect.

**Step 1: Run backend focused tests**

Run:

```bash
pytest tests/test_agent_capabilities.py tests/test_agent_service.py tests/test_agent_runtime.py tests/test_agent_runs.py tests/test_agents_api.py tests/test_openapi_contract.py -v
```

Expected: PASS.

**Step 2: Run frontend focused tests**

Run:

```bash
cd frontend && npm test -- --run src/features/agents/api.test.ts src/features/agents/hooks.test.tsx src/features/agents/__tests__/AgentForm.test.tsx src/features/agents/__tests__/AgentPages.test.tsx src/features/agents/__tests__/AgentChatPage.test.tsx
```

Expected: PASS.

**Step 3: Commit fixes only if needed**

If verification reveals implementation defects, make minimal fixes and commit:

```bash
git add <changed-files>
git commit -m "fix: stabilize agent capabilities chat"
```

Do not broaden scope.
