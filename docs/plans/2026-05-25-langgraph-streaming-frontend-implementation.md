# LangGraph Streaming Frontend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a FastAPI + LangGraph streaming endpoint and a frontend adapter that renders multi-node graph execution with per-node progress, token routing, persisted checkpoints, and final assistant output.

**Architecture:** The backend owns the compiled LangGraph graph and streams normalized SSE events from `graph.astream(...)`. A thin adapter converts raw LangGraph stream chunks into a stable event envelope. The frontend consumes the event envelope with a reducer and hook, keeping node runtime state separate from final chat messages.

**Tech Stack:** Python 3.12, FastAPI, LangGraph, Postgres checkpointer for production persistence, pytest, httpx, TypeScript, React, Vitest.

---

## Preconditions

- Start from the existing repository at `/Users/wanyaozhong/Projects/change-quality-agent`.
- Read `docs/plans/2026-05-25-langgraph-streaming-frontend-design.md` before implementing.
- Use TDD for each task: write the failing test first, run it, implement, run it again.
- Commit after each task or small group of tightly related files.
- Do not add a production LLM provider call in this plan. Use deterministic graph nodes first so streaming, persistence, and UI behavior can be tested without secrets.

## Task 1: Add Runtime And Test Dependencies

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`

**Step 1: Add backend dependencies**

Run:

```bash
uv add uvicorn langgraph-checkpoint-postgres "psycopg[binary,pool]"
```

Expected: `pyproject.toml` includes the new runtime dependencies and `uv.lock` is updated.

**Step 2: Add backend test dependencies**

Run:

```bash
uv add --dev pytest pytest-asyncio httpx
```

Expected: `pyproject.toml` contains a dev dependency group and `uv.lock` is updated.

**Step 3: Verify dependency resolution**

Run:

```bash
uv run python -c "import fastapi, langgraph; print('ok')"
```

Expected: prints `ok`.

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add streaming runtime dependencies"
```

## Task 2: Create FastAPI App Skeleton

**Files:**
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `app/api/__init__.py`
- Create: `app/api/routes/__init__.py`
- Create: `app/api/routes/health.py`
- Create: `tests/test_health.py`

**Step 1: Write the failing health test**

Create `tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_health.py -v
```

Expected: FAIL because `app.main` does not exist.

**Step 3: Implement the minimal app**

Create `app/api/routes/health.py`:

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

Create `app/main.py`:

```python
from fastapi import FastAPI

from app.api.routes.health import router as health_router


app = FastAPI(title="Change Quality Agent")
app.include_router(health_router)
```

Create empty package files:

```text
app/__init__.py
app/api/__init__.py
app/api/routes/__init__.py
```

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_health.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app tests/test_health.py
git commit -m "feat: add FastAPI app skeleton"
```

## Task 3: Define The Streaming Event Schema

**Files:**
- Create: `app/streaming/__init__.py`
- Create: `app/streaming/events.py`
- Create: `tests/streaming/test_events.py`

**Step 1: Write failing schema tests**

Create `tests/streaming/test_events.py`:

```python
from app.streaming.events import StreamEvent


def test_stream_event_defaults_optional_fields():
    event = StreamEvent(
        type="messages",
        node="generate_answer",
        thread_id="thread-1",
        run_id="run-1",
        sequence=1,
        payload={"content": "hi"},
    )

    assert event.checkpoint_id is None
    assert event.task_id is None
    assert event.parent_node is None
    assert event.payload == {"content": "hi"}


def test_stream_event_serializes_to_json():
    event = StreamEvent(
        type="done",
        node=None,
        thread_id="thread-1",
        run_id="run-1",
        sequence=2,
        payload={},
    )

    assert '"type":"done"' in event.model_dump_json()
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/streaming/test_events.py -v
```

Expected: FAIL because `app.streaming.events` does not exist.

**Step 3: Implement the schema**

Create `app/streaming/events.py`:

```python
from typing import Any, Literal

from pydantic import BaseModel, Field


StreamEventType = Literal[
    "tasks",
    "messages",
    "updates",
    "custom",
    "checkpoints",
    "error",
    "done",
]


class StreamEvent(BaseModel):
    type: StreamEventType
    node: str | None
    thread_id: str
    run_id: str
    sequence: int = Field(ge=0)
    payload: dict[str, Any]
    checkpoint_id: str | None = None
    task_id: str | None = None
    parent_node: str | None = None
```

Create empty package file:

```text
app/streaming/__init__.py
```

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/streaming/test_events.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/streaming tests/streaming/test_events.py
git commit -m "feat: define streaming event schema"
```

## Task 4: Adapt Raw LangGraph Stream Chunks

**Files:**
- Create: `app/streaming/langgraph_adapter.py`
- Create: `tests/streaming/test_langgraph_adapter.py`

**Step 1: Write failing adapter tests**

Create `tests/streaming/test_langgraph_adapter.py`:

```python
from app.streaming.langgraph_adapter import adapt_langgraph_item


def test_adapts_message_tuple_and_extracts_node():
    item = (
        "messages",
        (
            {"content": "h"},
            {"langgraph_node": "generate_answer"},
        ),
    )

    event = adapt_langgraph_item(
        item,
        thread_id="thread-1",
        run_id="run-1",
        sequence=0,
    )

    assert event.type == "messages"
    assert event.node == "generate_answer"
    assert event.payload["content"] == "h"


def test_adapts_update_chunk_and_extracts_single_node():
    item = ("updates", {"retrieve": {"documents": ["a", "b"]}})

    event = adapt_langgraph_item(
        item,
        thread_id="thread-1",
        run_id="run-1",
        sequence=1,
    )

    assert event.type == "updates"
    assert event.node == "retrieve"
    assert event.payload["writes"] == {"retrieve": {"documents": ["a", "b"]}}


def test_adapts_subgraph_tuple_with_parent_node():
    item = (
        ("planner:abc",),
        "updates",
        {"analyze": {"analysis": "ok"}},
    )

    event = adapt_langgraph_item(
        item,
        thread_id="thread-1",
        run_id="run-1",
        sequence=2,
    )

    assert event.type == "updates"
    assert event.parent_node == "planner"
    assert event.node == "analyze"
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/streaming/test_langgraph_adapter.py -v
```

Expected: FAIL because the adapter does not exist.

**Step 3: Implement the adapter**

Create `app/streaming/langgraph_adapter.py`:

```python
from collections.abc import Sequence
from typing import Any

from app.streaming.events import StreamEvent, StreamEventType


def adapt_langgraph_item(
    item: Any,
    *,
    thread_id: str,
    run_id: str,
    sequence: int,
) -> StreamEvent:
    namespace, mode, chunk = _split_stream_item(item)
    node = _extract_node(mode, chunk)

    return StreamEvent(
        type=mode,
        node=node,
        thread_id=thread_id,
        run_id=run_id,
        sequence=sequence,
        payload=_payload_for(mode, chunk),
        checkpoint_id=_extract_checkpoint_id(chunk),
        task_id=_extract_task_id(chunk),
        parent_node=_extract_parent_node(namespace),
    )


def _split_stream_item(item: Any) -> tuple[tuple[str, ...], StreamEventType, Any]:
    if isinstance(item, tuple) and len(item) == 3:
        namespace, mode, chunk = item
        return tuple(namespace), mode, chunk

    if isinstance(item, tuple) and len(item) == 2:
        mode, chunk = item
        return (), mode, chunk

    raise ValueError(f"Unsupported LangGraph stream item: {item!r}")


def _extract_node(mode: str, chunk: Any) -> str | None:
    if mode == "messages":
        metadata = _message_metadata(chunk)
        node = metadata.get("langgraph_node")
        return node if isinstance(node, str) else None

    if mode == "updates" and isinstance(chunk, dict) and len(chunk) == 1:
        key = next(iter(chunk))
        return key if isinstance(key, str) else None

    if isinstance(chunk, dict):
        for key in ("node", "name"):
            value = chunk.get(key)
            if isinstance(value, str):
                return value

    return None


def _payload_for(mode: str, chunk: Any) -> dict[str, Any]:
    if mode == "messages":
        message, metadata = _message_parts(chunk)
        content = _message_content(message)
        return {
            "content": content,
            "message": message,
            "metadata": metadata,
        }

    if mode == "updates":
        return {"writes": chunk}

    if isinstance(chunk, dict):
        return chunk

    return {"data": chunk}


def _message_parts(chunk: Any) -> tuple[Any, dict[str, Any]]:
    if isinstance(chunk, tuple) and len(chunk) == 2:
        message, metadata = chunk
        if isinstance(metadata, dict):
            return message, metadata
        return message, {}
    return chunk, {}


def _message_metadata(chunk: Any) -> dict[str, Any]:
    return _message_parts(chunk)[1]


def _message_content(message: Any) -> str:
    if isinstance(message, dict):
        content = message.get("content")
        return content if isinstance(content, str) else ""
    content = getattr(message, "content", "")
    return content if isinstance(content, str) else ""


def _extract_checkpoint_id(chunk: Any) -> str | None:
    if not isinstance(chunk, dict):
        return None
    value = chunk.get("checkpoint_id")
    return value if isinstance(value, str) else None


def _extract_task_id(chunk: Any) -> str | None:
    if not isinstance(chunk, dict):
        return None
    value = chunk.get("task_id") or chunk.get("id")
    return value if isinstance(value, str) else None


def _extract_parent_node(namespace: Sequence[str]) -> str | None:
    if not namespace:
        return None
    head = namespace[0]
    return head.split(":", maxsplit=1)[0]
```

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/streaming/test_langgraph_adapter.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/streaming/langgraph_adapter.py tests/streaming/test_langgraph_adapter.py
git commit -m "feat: adapt LangGraph stream events"
```

## Task 5: Encode Server-Sent Events

**Files:**
- Create: `app/streaming/sse.py`
- Create: `tests/streaming/test_sse.py`

**Step 1: Write failing SSE tests**

Create `tests/streaming/test_sse.py`:

```python
from app.streaming.events import StreamEvent
from app.streaming.sse import encode_sse


def test_encode_sse_uses_event_type_and_json_data():
    event = StreamEvent(
        type="done",
        node=None,
        thread_id="thread-1",
        run_id="run-1",
        sequence=3,
        payload={},
    )

    encoded = encode_sse(event)

    assert encoded.startswith("event: done\n")
    assert 'data: {"type":"done"' in encoded
    assert encoded.endswith("\n\n")
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/streaming/test_sse.py -v
```

Expected: FAIL because `encode_sse` does not exist.

**Step 3: Implement SSE encoding**

Create `app/streaming/sse.py`:

```python
from app.streaming.events import StreamEvent


def encode_sse(event: StreamEvent) -> str:
    return f"event: {event.type}\ndata: {event.model_dump_json()}\n\n"
```

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/streaming/test_sse.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/streaming/sse.py tests/streaming/test_sse.py
git commit -m "feat: encode streaming events as SSE"
```

## Task 6: Build A Deterministic LangGraph For Local Development

**Files:**
- Create: `app/graph/__init__.py`
- Create: `app/graph/state.py`
- Create: `app/graph/factory.py`
- Create: `tests/graph/test_factory.py`

**Step 1: Write a failing graph test**

Create `tests/graph/test_factory.py`:

```python
import pytest

from app.graph.factory import build_graph


@pytest.mark.asyncio
async def test_graph_streams_updates_for_pipeline_nodes():
    graph = build_graph()
    config = {"configurable": {"thread_id": "test-thread"}}

    events = [
        item
        async for item in graph.astream(
            {"messages": [{"role": "user", "content": "Review this change"}]},
            config=config,
            stream_mode=["updates"],
        )
    ]

    assert any("classify" in chunk for chunk in events)
    assert any("retrieve" in chunk for chunk in events)
    assert any("analyze" in chunk for chunk in events)
    assert any("generate_answer" in chunk for chunk in events)
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/graph/test_factory.py -v
```

Expected: FAIL because `app.graph.factory` does not exist.

**Step 3: Implement the deterministic graph**

Create `app/graph/state.py`:

```python
from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class ChangeQualityState(TypedDict, total=False):
    messages: Annotated[list[dict[str, Any]], add_messages]
    classification: str
    documents: list[str]
    analysis: str
```

Create `app/graph/factory.py`:

```python
from langgraph.graph import END, START, StateGraph

from app.graph.state import ChangeQualityState


async def classify(state: ChangeQualityState) -> dict[str, str]:
    return {"classification": "code-review"}


async def retrieve(state: ChangeQualityState) -> dict[str, list[str]]:
    return {"documents": ["diff-summary", "project-guidelines"]}


async def analyze(state: ChangeQualityState) -> dict[str, str]:
    return {"analysis": "No blocking risks found in deterministic sample."}


async def generate_answer(state: ChangeQualityState) -> dict[str, list[dict[str, str]]]:
    return {
        "messages": [
            {
                "role": "assistant",
                "content": "Sample review complete.",
            }
        ]
    }


def build_graph(checkpointer=None):
    builder = StateGraph(ChangeQualityState)
    builder.add_node("classify", classify)
    builder.add_node("retrieve", retrieve)
    builder.add_node("analyze", analyze)
    builder.add_node("generate_answer", generate_answer)
    builder.add_edge(START, "classify")
    builder.add_edge("classify", "retrieve")
    builder.add_edge("retrieve", "analyze")
    builder.add_edge("analyze", "generate_answer")
    builder.add_edge("generate_answer", END)
    return builder.compile(checkpointer=checkpointer)
```

Create empty package file:

```text
app/graph/__init__.py
```

**Step 4: Run test**

Run:

```bash
uv run pytest tests/graph/test_factory.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/graph tests/graph/test_factory.py
git commit -m "feat: add deterministic LangGraph pipeline"
```

## Task 7: Add Checkpointer Configuration

**Files:**
- Create: `app/settings.py`
- Create: `app/graph/checkpointing.py`
- Create: `tests/graph/test_checkpointing.py`

**Step 1: Write failing configuration tests**

Create `tests/graph/test_checkpointing.py`:

```python
from app.graph.checkpointing import build_checkpointer


def test_build_checkpointer_uses_memory_for_tests(monkeypatch):
    monkeypatch.delenv("LANGGRAPH_POSTGRES_URI", raising=False)

    checkpointer = build_checkpointer()

    assert checkpointer is not None
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/graph/test_checkpointing.py -v
```

Expected: FAIL because `app.graph.checkpointing` does not exist.

**Step 3: Implement checkpointer selection**

Create `app/settings.py`:

```python
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    langgraph_postgres_uri: str | None = None


def get_settings() -> Settings:
    return Settings(langgraph_postgres_uri=os.getenv("LANGGRAPH_POSTGRES_URI"))
```

Create `app/graph/checkpointing.py`:

```python
from langgraph.checkpoint.memory import InMemorySaver

from app.settings import get_settings


def build_checkpointer():
    settings = get_settings()
    if not settings.langgraph_postgres_uri:
        return InMemorySaver()

    # The Postgres saver is introduced in a later task because it needs an
    # async lifespan owner. Keep this function simple until app startup owns it.
    return InMemorySaver()
```

**Step 4: Run test**

Run:

```bash
uv run pytest tests/graph/test_checkpointing.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/settings.py app/graph/checkpointing.py tests/graph/test_checkpointing.py
git commit -m "feat: add checkpointer configuration"
```

## Task 8: Add The Streaming Run Endpoint

**Files:**
- Create: `app/api/routes/runs.py`
- Modify: `app/main.py`
- Create: `tests/api/test_runs_stream.py`

**Step 1: Write failing endpoint test**

Create `tests/api/test_runs_stream.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_runs_stream_returns_sse_events():
    client = TestClient(app)

    with client.stream(
        "POST",
        "/threads/thread-1/runs/stream",
        json={"messages": [{"role": "user", "content": "Review this"}]},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "event: updates" in body
    assert "event: done" in body
    assert '"thread_id":"thread-1"' in body
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/api/test_runs_stream.py -v
```

Expected: FAIL because the route does not exist.

**Step 3: Implement the endpoint**

Create `app/api/routes/runs.py`:

```python
from collections.abc import AsyncIterator
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.graph.checkpointing import build_checkpointer
from app.graph.factory import build_graph
from app.streaming.events import StreamEvent
from app.streaming.langgraph_adapter import adapt_langgraph_item
from app.streaming.sse import encode_sse

router = APIRouter(prefix="/threads/{thread_id}/runs", tags=["runs"])


@router.post("/stream")
async def stream_run(thread_id: str, input_state: dict) -> StreamingResponse:
    run_id = str(uuid4())

    async def event_iter() -> AsyncIterator[str]:
        graph = build_graph(checkpointer=build_checkpointer())
        config = {"configurable": {"thread_id": thread_id}}
        sequence = 0

        try:
            async for item in graph.astream(
                input_state,
                config=config,
                stream_mode=["tasks", "messages", "updates", "custom", "checkpoints"],
                subgraphs=True,
            ):
                event = adapt_langgraph_item(
                    item,
                    thread_id=thread_id,
                    run_id=run_id,
                    sequence=sequence,
                )
                sequence += 1
                yield encode_sse(event)

            yield encode_sse(
                StreamEvent(
                    type="done",
                    node=None,
                    thread_id=thread_id,
                    run_id=run_id,
                    sequence=sequence,
                    payload={},
                )
            )
        except Exception as exc:
            yield encode_sse(
                StreamEvent(
                    type="error",
                    node=None,
                    thread_id=thread_id,
                    run_id=run_id,
                    sequence=sequence,
                    payload={"message": str(exc)},
                )
            )

    return StreamingResponse(event_iter(), media_type="text/event-stream")
```

Modify `app/main.py`:

```python
from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.runs import router as runs_router


app = FastAPI(title="Change Quality Agent")
app.include_router(health_router)
app.include_router(runs_router)
```

**Step 4: Run endpoint test**

Run:

```bash
uv run pytest tests/api/test_runs_stream.py -v
```

Expected: PASS.

**Step 5: Run all backend tests**

Run:

```bash
uv run pytest -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add app/api/routes/runs.py app/main.py tests/api/test_runs_stream.py
git commit -m "feat: stream LangGraph runs over SSE"
```

## Task 9: Move Graph Construction Into App Lifespan

**Files:**
- Modify: `app/main.py`
- Modify: `app/api/routes/runs.py`
- Create: `tests/api/test_app_state.py`

**Step 1: Write failing app state test**

Create `tests/api/test_app_state.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_app_lifespan_sets_graph():
    with TestClient(app) as client:
        assert client.app.state.graph is not None
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/api/test_app_state.py -v
```

Expected: FAIL because `app.state.graph` is not initialized.

**Step 3: Implement lifespan-owned graph**

Modify `app/main.py`:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.runs import router as runs_router
from app.graph.checkpointing import build_checkpointer
from app.graph.factory import build_graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.checkpointer = build_checkpointer()
    app.state.graph = build_graph(checkpointer=app.state.checkpointer)
    yield


app = FastAPI(title="Change Quality Agent", lifespan=lifespan)
app.include_router(health_router)
app.include_router(runs_router)
```

Modify `app/api/routes/runs.py` to use `request.app.state.graph` instead of
building the graph inside every request:

```python
from collections.abc import AsyncIterator
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.streaming.events import StreamEvent
from app.streaming.langgraph_adapter import adapt_langgraph_item
from app.streaming.sse import encode_sse

router = APIRouter(prefix="/threads/{thread_id}/runs", tags=["runs"])


@router.post("/stream")
async def stream_run(
    request: Request,
    thread_id: str,
    input_state: dict,
) -> StreamingResponse:
    run_id = str(uuid4())

    async def event_iter() -> AsyncIterator[str]:
        graph = request.app.state.graph
        config = {"configurable": {"thread_id": thread_id}}
        sequence = 0

        try:
            async for item in graph.astream(
                input_state,
                config=config,
                stream_mode=["tasks", "messages", "updates", "custom", "checkpoints"],
                subgraphs=True,
            ):
                event = adapt_langgraph_item(
                    item,
                    thread_id=thread_id,
                    run_id=run_id,
                    sequence=sequence,
                )
                sequence += 1
                yield encode_sse(event)

            yield encode_sse(
                StreamEvent(
                    type="done",
                    node=None,
                    thread_id=thread_id,
                    run_id=run_id,
                    sequence=sequence,
                    payload={},
                )
            )
        except Exception as exc:
            yield encode_sse(
                StreamEvent(
                    type="error",
                    node=None,
                    thread_id=thread_id,
                    run_id=run_id,
                    sequence=sequence,
                    payload={"message": str(exc)},
                )
            )

    return StreamingResponse(event_iter(), media_type="text/event-stream")
```

**Step 4: Run tests**

Run:

```bash
uv run pytest tests/api/test_app_state.py tests/api/test_runs_stream.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/main.py app/api/routes/runs.py tests/api/test_app_state.py
git commit -m "refactor: initialize graph in app lifespan"
```

## Task 10: Add Production Postgres Saver Ownership

**Files:**
- Modify: `app/main.py`
- Modify: `app/graph/checkpointing.py`
- Create: `tests/graph/test_checkpointing_postgres.py`

**Step 1: Write a focused configuration test**

Create `tests/graph/test_checkpointing_postgres.py`:

```python
from app.graph.checkpointing import should_use_postgres


def test_should_use_postgres_when_uri_is_present():
    assert should_use_postgres("postgresql://user:pass@localhost/db")


def test_should_not_use_postgres_when_uri_is_missing():
    assert not should_use_postgres(None)
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/graph/test_checkpointing_postgres.py -v
```

Expected: FAIL because `should_use_postgres` does not exist.

**Step 3: Implement async saver ownership**

Modify `app/graph/checkpointing.py`:

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.settings import get_settings


def should_use_postgres(uri: str | None) -> bool:
    return bool(uri)


@asynccontextmanager
async def lifespan_checkpointer() -> AsyncIterator[object]:
    settings = get_settings()
    if not should_use_postgres(settings.langgraph_postgres_uri):
        yield InMemorySaver()
        return

    async with AsyncPostgresSaver.from_conn_string(
        settings.langgraph_postgres_uri
    ) as saver:
        await saver.setup()
        yield saver
```

Modify `app/main.py` to use `lifespan_checkpointer()`:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.runs import router as runs_router
from app.graph.checkpointing import lifespan_checkpointer
from app.graph.factory import build_graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with lifespan_checkpointer() as checkpointer:
        app.state.checkpointer = checkpointer
        app.state.graph = build_graph(checkpointer=checkpointer)
        yield


app = FastAPI(title="Change Quality Agent", lifespan=lifespan)
app.include_router(health_router)
app.include_router(runs_router)
```

Update older tests that import `build_checkpointer` to use `lifespan_checkpointer`
or delete the obsolete test if it only covered the temporary function.

**Step 4: Run backend tests**

Run:

```bash
uv run pytest -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/main.py app/graph/checkpointing.py tests/graph/test_checkpointing_postgres.py tests/graph/test_checkpointing.py
git commit -m "feat: own checkpointer lifecycle in app startup"
```

## Task 11: Add Frontend Reducer Package

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/src/lib/langgraphStream.ts`
- Create: `frontend/src/lib/langgraphStream.test.ts`
- Create: `frontend/tsconfig.json`

**Step 1: Create the frontend package metadata**

Create `frontend/package.json`:

```json
{
  "name": "change-quality-agent-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "vitest run",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^5.0.0",
    "vite": "^7.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "typescript": "^5.0.0",
    "vitest": "^4.0.0"
  }
}
```

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "jsx": "react-jsx",
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

**Step 2: Write failing reducer tests**

Create `frontend/src/lib/langgraphStream.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { initialGraphRunState, reduceGraphEvent } from "./langgraphStream";

describe("reduceGraphEvent", () => {
  it("routes message chunks to the producing node", () => {
    const state = reduceGraphEvent(initialGraphRunState(), {
      type: "messages",
      node: "generate_answer",
      thread_id: "thread-1",
      run_id: "run-1",
      sequence: 0,
      payload: { content: "hi" },
    });

    expect(state.nodes.generate_answer.streamText).toBe("hi");
    expect(state.nodes.generate_answer.status).toBe("running");
  });

  it("stores update writes without relying on arrival order", () => {
    const state = reduceGraphEvent(initialGraphRunState(), {
      type: "updates",
      node: "retrieve",
      thread_id: "thread-1",
      run_id: "run-1",
      sequence: 1,
      payload: { writes: { retrieve: { documents: ["a"] } } },
    });

    expect(state.nodes.retrieve.status).toBe("done");
    expect(state.values.retrieve).toEqual({ documents: ["a"] });
  });
});
```

**Step 3: Run tests to verify they fail**

Run:

```bash
cd frontend && npm install && npm test
```

Expected: FAIL because `langgraphStream.ts` does not exist.

**Step 4: Implement the reducer**

Create `frontend/src/lib/langgraphStream.ts`:

```ts
export type StreamEventType =
  | "tasks"
  | "messages"
  | "updates"
  | "custom"
  | "checkpoints"
  | "error"
  | "done";

export type StreamEvent = {
  type: StreamEventType;
  node: string | null;
  thread_id: string;
  run_id: string;
  sequence: number;
  payload: Record<string, unknown>;
  checkpoint_id?: string | null;
  task_id?: string | null;
  parent_node?: string | null;
};

export type NodeStatus = "idle" | "running" | "done" | "error";

export type NodeRuntime = {
  status: NodeStatus;
  streamText: string;
  value?: unknown;
  progress?: unknown;
  error?: string;
};

export type GraphRunState = {
  isRunning: boolean;
  messages: unknown[];
  nodes: Record<string, NodeRuntime>;
  values: Record<string, unknown>;
  checkpoints: StreamEvent[];
  error?: string;
};

const NODE_IDS = ["classify", "retrieve", "analyze", "generate_answer"] as const;

export function initialGraphRunState(): GraphRunState {
  return {
    isRunning: false,
    messages: [],
    nodes: Object.fromEntries(
      NODE_IDS.map((id) => [id, { status: "idle", streamText: "" }]),
    ),
    values: {},
    checkpoints: [],
  };
}

export function reduceGraphEvent(
  state: GraphRunState,
  event: StreamEvent,
): GraphRunState {
  const next: GraphRunState = {
    ...state,
    nodes: { ...state.nodes },
    values: { ...state.values },
    checkpoints: [...state.checkpoints],
  };

  if (event.type === "done") {
    next.isRunning = false;
    return next;
  }

  if (event.type === "error") {
    next.isRunning = false;
    next.error = String(event.payload.message ?? "Unknown stream error");
    if (event.node) {
      next.nodes[event.node] = {
        ...nodeState(next, event.node),
        status: "error",
        error: next.error,
      };
    }
    return next;
  }

  next.isRunning = true;

  if (event.type === "messages" && event.node) {
    const current = nodeState(next, event.node);
    next.nodes[event.node] = {
      ...current,
      status: "running",
      streamText: current.streamText + String(event.payload.content ?? ""),
    };
    return next;
  }

  if (event.type === "updates" && event.node) {
    const writes = event.payload.writes as Record<string, unknown> | undefined;
    const value = writes?.[event.node] ?? event.payload;
    next.nodes[event.node] = {
      ...nodeState(next, event.node),
      status: "done",
      value,
    };
    next.values[event.node] = value;
    return next;
  }

  if (event.type === "tasks" && event.node) {
    next.nodes[event.node] = {
      ...nodeState(next, event.node),
      status: "running",
    };
    return next;
  }

  if (event.type === "custom" && event.node) {
    next.nodes[event.node] = {
      ...nodeState(next, event.node),
      progress: event.payload,
    };
    return next;
  }

  if (event.type === "checkpoints") {
    next.checkpoints.push(event);
  }

  return next;
}

function nodeState(state: GraphRunState, node: string): NodeRuntime {
  return state.nodes[node] ?? { status: "idle", streamText: "" };
}
```

**Step 5: Run frontend tests**

Run:

```bash
cd frontend && npm test && npm run typecheck
```

Expected: PASS.

**Step 6: Commit**

```bash
git add frontend
git commit -m "feat: add frontend stream reducer"
```

## Task 12: Add React Streaming Hook

**Files:**
- Create: `frontend/src/hooks/useGraphRunStream.ts`
- Create: `frontend/src/hooks/useGraphRunStream.test.tsx`

**Step 1: Write failing hook tests**

Create `frontend/src/hooks/useGraphRunStream.test.tsx` with a minimal fetch/EventSource
mock or choose a hook testing helper already standard in the project. If no hook
testing helper exists, skip component rendering and test the exported parser from
the hook file instead.

Minimum parser test:

```ts
import { describe, expect, it } from "vitest";
import { parseSseDataLine } from "./useGraphRunStream";

describe("parseSseDataLine", () => {
  it("parses SSE data lines", () => {
    const event = parseSseDataLine(
      'data: {"type":"done","node":null,"thread_id":"t","run_id":"r","sequence":1,"payload":{}}',
    );

    expect(event.type).toBe("done");
  });
});
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd frontend && npm test -- src/hooks/useGraphRunStream.test.tsx
```

Expected: FAIL because the hook file does not exist.

**Step 3: Implement the parser and hook**

Create `frontend/src/hooks/useGraphRunStream.ts`:

```ts
import { useCallback, useReducer } from "react";
import {
  type GraphRunState,
  type StreamEvent,
  initialGraphRunState,
  reduceGraphEvent,
} from "../lib/langgraphStream";

export function parseSseDataLine(line: string): StreamEvent {
  if (!line.startsWith("data: ")) {
    throw new Error("Expected SSE data line");
  }
  return JSON.parse(line.slice("data: ".length)) as StreamEvent;
}

export function useGraphRunStream(apiBaseUrl: string) {
  const [state, dispatch] = useReducer(
    reduceGraphEvent,
    undefined,
    initialGraphRunState,
  );

  const submit = useCallback(
    async (threadId: string, input: Record<string, unknown>) => {
      const response = await fetch(
        `${apiBaseUrl}/threads/${threadId}/runs/stream`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(input),
        },
      );

      if (!response.body) {
        throw new Error("Streaming response did not include a body");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";

        for (const frame of frames) {
          const dataLine = frame.split("\n").find((line) => line.startsWith("data: "));
          if (dataLine) {
            dispatch(parseSseDataLine(dataLine));
          }
        }
      }
    },
    [apiBaseUrl],
  );

  return { ...(state as GraphRunState), submit };
}
```

**Step 4: Run frontend tests**

Run:

```bash
cd frontend && npm test && npm run typecheck
```

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/hooks
git commit -m "feat: add graph run streaming hook"
```

## Task 13: Add Pipeline UI Component

**Files:**
- Create: `frontend/src/components/PipelineRun.tsx`
- Create: `frontend/src/components/PipelineRun.test.tsx`

**Step 1: Write failing component test**

Use React Testing Library if the project adopts it. If it is not installed yet,
add it in this task:

```bash
cd frontend && npm install -D @testing-library/react @testing-library/jest-dom jsdom
```

Test that a node with streaming text renders its label and content.

**Step 2: Implement a compact component**

Create `frontend/src/components/PipelineRun.tsx`:

```tsx
import type { GraphRunState } from "../lib/langgraphStream";

const PIPELINE_NODES = [
  { id: "classify", label: "Classify" },
  { id: "retrieve", label: "Retrieve" },
  { id: "analyze", label: "Analyze" },
  { id: "generate_answer", label: "Answer" },
] as const;

type Props = {
  run: GraphRunState;
};

export function PipelineRun({ run }: Props) {
  return (
    <section aria-label="Pipeline run">
      {PIPELINE_NODES.map((node) => {
        const runtime = run.nodes[node.id];
        return (
          <article key={node.id} data-status={runtime.status}>
            <header>{node.label}</header>
            {runtime.streamText ? <p>{runtime.streamText}</p> : null}
            {runtime.error ? <p role="alert">{runtime.error}</p> : null}
          </article>
        );
      })}
    </section>
  );
}
```

**Step 3: Run frontend tests**

Run:

```bash
cd frontend && npm test && npm run typecheck
```

Expected: PASS.

**Step 4: Commit**

```bash
git add frontend/src/components frontend/package.json frontend/package-lock.json
git commit -m "feat: render LangGraph pipeline progress"
```

## Task 14: Add End-To-End Smoke Verification

**Files:**
- Create: `scripts/smoke_stream.py`
- Create: `docs/streaming.md`

**Step 1: Add a smoke script**

Create `scripts/smoke_stream.py`:

```python
import httpx


def main() -> None:
    with httpx.stream(
        "POST",
        "http://127.0.0.1:8000/threads/smoke-thread/runs/stream",
        json={"messages": [{"role": "user", "content": "Review this"}]},
        timeout=30,
    ) as response:
        response.raise_for_status()
        body = "".join(response.iter_text())

    assert "event: updates" in body
    assert "event: done" in body
    print("stream smoke ok")


if __name__ == "__main__":
    main()
```

**Step 2: Add operator docs**

Create `docs/streaming.md` with:

```markdown
# Streaming Runs

Start the API:

```bash
uv run uvicorn app.main:app --reload
```

Run the smoke check:

```bash
uv run python scripts/smoke_stream.py
```

Production persistence uses `LANGGRAPH_POSTGRES_URI`. Local development falls
back to in-memory checkpointing.
```

**Step 3: Run full verification**

Terminal 1:

```bash
uv run uvicorn app.main:app --reload
```

Terminal 2:

```bash
uv run pytest -v
uv run python scripts/smoke_stream.py
cd frontend && npm test && npm run typecheck
```

Expected:

- Backend tests pass.
- Smoke script prints `stream smoke ok`.
- Frontend tests and typecheck pass.

**Step 4: Commit**

```bash
git add scripts/smoke_stream.py docs/streaming.md
git commit -m "docs: document streaming run workflow"
```

## Final Verification

Run:

```bash
git status --short
uv run pytest -v
cd frontend && npm test && npm run typecheck
```

Expected:

- `git status --short` has no unrelated unstaged changes.
- Backend tests pass.
- Frontend tests pass.
- TypeScript typecheck passes.

## Execution Notes

- If the team chooses LangGraph Platform later, replace the local frontend hook
  with the official React `useStream` hook and map `stream.messages`,
  `stream.values`, and `getMessagesMetadata` into the same UI components.
- If the graph later uses a real streaming chat model, keep the event envelope
  unchanged and update only graph node implementations.
- If frontend stack already exists elsewhere, port `langgraphStream.ts`,
  `useGraphRunStream.ts`, and `PipelineRun.tsx` into that app instead of keeping
  the standalone `frontend/` folder.
