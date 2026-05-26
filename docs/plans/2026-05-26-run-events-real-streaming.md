# Run Events Real Streaming Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace coarse run completion events with real persisted streaming events for SOP and agent runs while keeping the existing `/api/runs/{run_id}/events?after=N` SSE contract.

**Architecture:** Use 方案 1: runtime streams are normalized and persisted to `run_events`; the current SSE endpoint continues to replay and follow durable events from Postgres. The frontend reducer consumes both incremental `messages.payload.delta` events and final `messages.payload.messages` events without duplicating text.

**Tech Stack:** FastAPI, SQLAlchemy async sessions, Postgres 13, LangChain/LangGraph async streaming, React 19, TypeScript, Vite, Vitest, Streamdown.

---

## Context

The current backend endpoint `GET /api/runs/{run_id}/events?after=N` is already an SSE stream, but it polls persisted `run_events` rows. The missing piece is real upstream streaming: `AgentRuntime` currently calls `ainvoke`, and SOP quality uses `run_mock_sop_quality_graph` with `ainvoke`. This plan keeps durable event replay as the source of truth and adds real stream production behind it.

Do not implement 方案 2 in this plan. 方案 2, in-process broadcast plus DB persistence, remains in `TODO.md` under optimization items.

## Task 1: Document Postgres 13 Full-Stack Debug Flow

**Files:**
- Modify: `README.md`
- Modify: `docs/frontend.md`
- Test: manual command verification only

**Step 1: Write the documentation change**

Add a short "Full-stack SOP debugging" section to `README.md`:

````markdown
## Full-Stack SOP Debugging

Use Postgres 13 for local end-to-end SOP run debugging.

```bash
docker run -d --name cqa-postgres-13 \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=change_quality_agent \
  -p 5432:5432 \
  postgres:13

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/change_quality_agent \
  uv run alembic upgrade head

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/change_quality_agent \
  uv run fastapi dev --host 127.0.0.1 --port 8000

cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```
````

In `docs/frontend.md`, replace any generic local DB wording for this flow with Postgres 13.

**Step 2: Verify docs render as plain markdown**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

**Step 3: Commit**

```bash
git add README.md docs/frontend.md
git commit -m "docs: add Postgres 13 SOP debug flow"
```

## Task 2: Add Runtime Stream Event Types

**Files:**
- Modify: `agent/react_runtime.py`
- Test: `tests/test_agent_runtime.py`

**Step 1: Write failing tests**

Add tests for a fake agent that exposes `astream`.

```python
@pytest.mark.asyncio
async def test_agent_runtime_stream_yields_message_deltas() -> None:
    class FakeAgent:
        async def astream(self, payload, stream_mode=None):
            yield ("messages", ("alpha", {"langgraph_node": "agent"}))
            yield ("messages", ("beta", {"langgraph_node": "agent"}))

    runtime = AgentRuntime(
        create_agent=lambda **kwargs: FakeAgent(),
        model_factory=lambda *args, **kwargs: object(),
    )

    chunks = [
        chunk
        async for chunk in runtime.stream(version=FakeVersion(), messages=[])
    ]

    assert [chunk["type"] for chunk in chunks] == ["messages", "messages"]
    assert [chunk["node"] for chunk in chunks] == ["agent", "agent"]
    assert [chunk["payload"]["delta"] for chunk in chunks] == ["alpha", "beta"]
```

Add a second test for fallback when `astream` is missing:

```python
@pytest.mark.asyncio
async def test_agent_runtime_stream_falls_back_to_final_run_output() -> None:
    class FakeAgent:
        async def ainvoke(self, payload):
            return {"messages": [{"role": "assistant", "content": "done"}]}

    runtime = AgentRuntime(
        create_agent=lambda **kwargs: FakeAgent(),
        model_factory=lambda *args, **kwargs: object(),
    )

    chunks = [
        chunk
        async for chunk in runtime.stream(version=FakeVersion(), messages=[])
    ]

    assert chunks == [
        {
            "type": "messages",
            "node": "agent",
            "payload": {
                "final": True,
                "messages": [{"role": "assistant", "content": "done"}],
            },
        }
    ]
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run python -m pytest tests/test_agent_runtime.py -q
```

Expected: FAIL because `AgentRuntime.stream` does not exist.

**Step 3: Implement minimal runtime stream**

In `agent/react_runtime.py`, add:

```python
    async def stream(
        self,
        *,
        version: Any,
        messages: list[dict[str, Any]],
    ):
        tools = self._tool_resolver.resolve(
            list(getattr(version, "tool_allowlist", [])),
            list(getattr(version, "mcp_server_ids", [])),
        )
        if inspect.isawaitable(tools):
            tools = await tools
        model_config = getattr(version, "model_config", {}) or {}
        model = self._model_factory(version.model, **dict(model_config))
        agent = self._create_agent(
            model=model,
            tools=tools,
            system_prompt=version.system_prompt,
        )

        astream = getattr(agent, "astream", None)
        if astream is None:
            result = await self._invoke(agent, {"messages": messages})
            output = to_jsonable(result) if isinstance(result, Mapping) else {}
            yield {
                "type": "messages",
                "node": "agent",
                "payload": {
                    "final": True,
                    "messages": _extract_messages(output),
                },
            }
            return

        async for chunk_type, chunk in astream(
            {"messages": messages},
            stream_mode=["messages", "updates", "custom"],
        ):
            yield runtime_stream_event(chunk_type, chunk)
```

Add a small helper that extracts string deltas from message chunks:

```python
def runtime_stream_event(chunk_type: str, chunk: object) -> dict[str, Any]:
    event = normalize_langgraph_chunk(
        chunk_type=chunk_type,
        chunk=chunk,
        run_id="",
        thread_id="",
        sequence=0,
    )
    payload = dict(event["payload"])
    if chunk_type == "messages":
        payload["delta"] = _message_delta(chunk)
    return {
        "type": event["type"],
        "node": event["node"] or "agent",
        "checkpoint_id": event["checkpoint_id"],
        "task_id": event["task_id"],
        "payload": payload,
    }
```

Import `normalize_langgraph_chunk` from `app.services.run_events`. Keep this helper independent from database concerns.

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run python -m pytest tests/test_agent_runtime.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add agent/react_runtime.py tests/test_agent_runtime.py
git commit -m "feat: stream runtime events from agents"
```

## Task 3: Persist Agent Runtime Stream Events

**Files:**
- Modify: `app/services/agents.py`
- Test: `tests/test_agent_test_run_executor.py`

**Step 1: Write failing tests**

Add a fake streaming runtime:

```python
class FakeStreamingRuntime:
    async def stream(self, *, version, messages):
        yield {
            "type": "messages",
            "node": "agent",
            "payload": {"delta": "alpha"},
        }
        yield {
            "type": "messages",
            "node": "agent",
            "payload": {"delta": "beta"},
        }
        yield {
            "type": "messages",
            "node": "agent",
            "payload": {
                "final": True,
                "messages": [{"role": "assistant", "content": "alphabeta"}],
            },
        }
```

Then add:

```python
@pytest.mark.asyncio
async def test_run_agent_test_persists_stream_events_before_done() -> None:
    version = FakeVersion(version_number=7)
    run = FakeRun(version)
    run_repository = FakeRunRepository(run)
    agent_repository = FakeAgentRepository(version)

    await run_agent_test(
        run.id,
        run_repository=run_repository,
        agent_repository=agent_repository,
        runtime=FakeStreamingRuntime(),
    )

    assert [event["event_type"] for event in run_repository.events] == [
        "custom",
        "messages",
        "messages",
        "messages",
        "done",
    ]
    assert run_repository.events[1]["payload"] == {"delta": "alpha"}
    assert run_repository.events[3]["payload"] == {
        "final": True,
        "messages": [{"role": "assistant", "content": "alphabeta"}],
    }
    assert run_repository.terminal[0] == RunStatus.success
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run python -m pytest tests/test_agent_test_run_executor.py::test_run_agent_test_persists_stream_events_before_done -q
```

Expected: FAIL because `run_agent_test` still calls `runtime.run`.

**Step 3: Implement stream consumption**

In `app/services/agents.py`, replace the single `runtime.run` call with a streaming loop:

```python
        stream = getattr(runtime, "stream", None)
        if stream is None:
            result = await runtime.run(
                version=version,
                messages=list(run.subject_snapshot.get("messages", [])),
            )
            result_messages = to_jsonable(result.messages)
            raw_graph_output = to_jsonable(result.raw_output)
            await run_repository.append_event(
                run_id,
                event_type="messages",
                thread_id=run.thread_id,
                payload={"messages": result_messages},
                node="agent",
            )
        else:
            result_messages: list[dict[str, Any]] = []
            raw_events: list[dict[str, Any]] = []
            async for event in stream(
                version=version,
                messages=list(run.subject_snapshot.get("messages", [])),
            ):
                event_payload = to_jsonable(event.get("payload", {}))
                raw_events.append(to_jsonable(event))
                await run_repository.append_event(
                    run_id,
                    event_type=str(event.get("type") or "custom"),
                    thread_id=run.thread_id,
                    payload=event_payload,
                    node=event.get("node") if isinstance(event.get("node"), str) else None,
                    checkpoint_id=event.get("checkpoint_id") if isinstance(event.get("checkpoint_id"), str) else None,
                    task_id=event.get("task_id") if isinstance(event.get("task_id"), str) else None,
                )
                await _commit_if_available(run_repository)
                if isinstance(event_payload, dict) and isinstance(event_payload.get("messages"), list):
                    result_messages = to_jsonable(event_payload["messages"])
            raw_graph_output = {"stream_events": raw_events}
```

Keep the existing fallback path for tests and runtimes without `stream`.

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run python -m pytest tests/test_agent_test_run_executor.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/services/agents.py tests/test_agent_test_run_executor.py
git commit -m "feat: persist agent streaming events"
```

## Task 4: Stream SOP Quality Graph Events

**Files:**
- Modify: `agent/graph.py`
- Modify: `app/services/sop_quality.py`
- Test: `tests/test_graph_runner.py`

**Step 1: Write failing tests**

Add a test that expects SOP run events to include message deltas before `done`:

```python
@pytest.mark.asyncio
async def test_sop_quality_graph_persists_streaming_messages() -> None:
    repository = FakeRunRepository()

    await run_sop_quality_graph(repository.run.id, repository)

    event_types = [event["event_type"] for event in repository.events]
    assert event_types == ["custom", "messages", "updates", "done"]
    assert repository.events[1]["payload"]["delta"]
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run python -m pytest tests/test_graph_runner.py::test_sop_quality_graph_persists_streaming_messages -q
```

Expected: FAIL because SOP graph currently only appends `custom`, `updates`, and `done`.

**Step 3: Implement minimal SOP stream event**

In `agent/graph.py`, add a streaming wrapper around the existing graph:

```python
async def stream_mock_sop_quality_graph(
    *,
    run_id: str,
    sop_snapshot: dict[str, Any],
):
    yield {
        "type": "messages",
        "node": "validate_sop",
        "payload": {"delta": "Loading SOP snapshot...\n"},
    }
    raw_graph_output = await run_mock_sop_quality_graph(
        run_id=run_id,
        sop_snapshot=sop_snapshot,
    )
    yield {
        "type": "updates",
        "node": "validate_sop",
        "payload": {"status": raw_graph_output["status"]},
    }
```

In `app/services/sop_quality.py`, consume this stream and persist each event before terminal `done`.

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run python -m pytest tests/test_graph_runner.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add agent/graph.py app/services/sop_quality.py tests/test_graph_runner.py
git commit -m "feat: stream SOP quality events"
```

## Task 5: Keep SSE Replay Contract Stable

**Files:**
- Modify: `tests/test_runs_api.py`
- Optionally modify: `app/api/v1/runs.py`

**Step 1: Write replay tests for message deltas**

Add:

```python
@pytest.mark.asyncio
async def test_events_replay_streaming_message_deltas(override_repository: FakeRun) -> None:
    override_repository.run.events = [
        FakeEvent(1, override_repository.id, "messages", payload={"delta": "alpha"}),
        FakeEvent(2, override_repository.id, "messages", payload={"delta": "beta"}),
        FakeEvent(3, override_repository.id, "done", payload={"status": "done"}),
    ]

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/runs/{override_repository.id}/events?after=1")

    assert response.status_code == 200
    assert "id: 2" in response.text
    assert '"delta": "beta"' in response.text
    assert "event: done" in response.text
```

**Step 2: Run test**

Run:

```bash
uv run python -m pytest tests/test_runs_api.py -q
```

Expected: PASS without production changes. If it fails, fix only the SSE serialization path in `app/api/v1/runs.py`.

**Step 3: Commit**

```bash
git add tests/test_runs_api.py app/api/v1/runs.py
git commit -m "test: cover streaming event replay"
```

## Task 6: Frontend Final Message Compatibility

**Files:**
- Modify: `frontend/src/features/runs/reducer.ts`
- Test: `frontend/src/features/runs/reducer.test.ts`

**Step 1: Keep or add reducer tests**

Ensure these tests exist:

```ts
it("uses final assistant messages to replace partial stream text", () => {
  const streaming = reduceRunEvent(
    createInitialRunViewState(),
    event({
      type: "messages",
      node: "check_steps",
      sequence: 2,
      payload: { delta: "alpha\nbet" },
    }),
  );

  const state = reduceRunEvent(
    streaming,
    event({
      type: "messages",
      node: "check_steps",
      sequence: 3,
      payload: {
        final: true,
        messages: [
          { role: "user", content: "check this SOP" },
          { role: "assistant", content: "alpha\nbeta\ngamma" },
        ],
      },
    }),
  );

  expect(state.nodes.check_steps?.streamText).toBe("alpha\nbeta\ngamma");
});
```

Add the duplicate prevention test:

```ts
it("does not duplicate final assistant messages after complete deltas", () => {
  const streaming = reduceRunEvent(
    createInitialRunViewState(),
    event({
      type: "messages",
      node: "check_steps",
      sequence: 2,
      payload: { delta: "alpha\nbeta\ngamma" },
    }),
  );

  const state = reduceRunEvent(
    streaming,
    event({
      type: "messages",
      node: "check_steps",
      sequence: 3,
      payload: {
        final: true,
        messages: [{ role: "assistant", content: "alpha\nbeta\ngamma" }],
      },
    }),
  );

  expect(state.nodes.check_steps?.streamText).toBe("alpha\nbeta\ngamma");
});
```

**Step 2: Run test to verify it fails if the reducer is not yet adapted**

Run:

```bash
cd frontend
npm run test -- --run src/features/runs/reducer.test.ts
```

Expected before implementation: FAIL because final `messages` does not update `streamText`.

**Step 3: Implement reducer final-message handling**

In `frontend/src/features/runs/reducer.ts`, ensure `messages` events:

- append `payload.delta`, `payload.text`, or `payload.content` when no final message exists.
- extract final assistant content from `payload.messages`.
- replace partial text when final text starts with the partial text.
- avoid appending the final text when it already equals the current stream text.

**Step 4: Run frontend tests**

Run:

```bash
cd frontend
npm run test -- --run
npm run build
```

Expected: all tests pass and Vite build succeeds. A large chunk warning is acceptable unless it is new and tied to this change.

**Step 5: Commit**

```bash
git add frontend/src/features/runs/reducer.ts frontend/src/features/runs/reducer.test.ts
git commit -m "feat: render final streamed messages"
```

## Task 7: Full-Stack SOP Debug Verification

**Files:**
- Test only; no source files expected.

**Step 1: Start Postgres 13**

Run:

```bash
docker run -d --name cqa-postgres-13 \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=change_quality_agent \
  -p 5432:5432 \
  postgres:13
```

Expected: container ID printed. If the container already exists, run `docker start cqa-postgres-13`.

**Step 2: Migrate database**

Run:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/change_quality_agent \
  uv run alembic upgrade head
```

Expected: migration reaches head without errors.

**Step 3: Start backend**

Run:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/change_quality_agent \
  uv run fastapi dev --host 127.0.0.1 --port 8000
```

Expected: backend listens on `http://127.0.0.1:8000`.

**Step 4: Start frontend**

Run in a second terminal:

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Expected: frontend listens on `http://127.0.0.1:5173`.

**Step 5: Verify API flow**

Run:

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/api/sop/environments
curl -sS 'http://127.0.0.1:8000/api/sop/release-checklist?env=dev'
curl -sS -X POST 'http://127.0.0.1:8000/api/sop/release-checklist/runs?env=dev'
```

Expected: final command returns `202` JSON with `run_id`, `status_url`, and `events_url`.

**Step 6: Verify SSE events**

Run:

```bash
curl -N 'http://127.0.0.1:8000/api/runs/<run_id>/events?after=0'
```

Expected:

- `event: custom`
- one or more `event: messages` with `payload.delta`
- `event: updates`
- `event: done`

**Step 7: Verify browser UI**

Open `http://127.0.0.1:5173`, start SOP `release-checklist`, and confirm:

- The run observer appears.
- Assistant content grows before terminal completion.
- Terminal status becomes success.
- Refreshing the page does not duplicate text.
- Recent runs still load.

**Step 8: Commit any documentation fixes only**

If the verification uncovers doc-only corrections:

```bash
git add README.md docs/frontend.md
git commit -m "docs: clarify SOP streaming debug flow"
```

## Task 8: Final Verification

**Files:**
- No source files expected.

**Step 1: Run backend tests**

Run:

```bash
uv run python -m pytest -q
```

Expected: PASS.

**Step 2: Run frontend tests and build**

Run:

```bash
cd frontend
npm run test -- --run
npm run build
```

Expected: PASS and build succeeds.

**Step 3: Check worktree status**

Run:

```bash
git status --short
```

Expected: no unstaged or uncommitted changes.
