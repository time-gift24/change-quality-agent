# Unified Agent Session Streaming Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a shared `sessions/messages` transcript foundation and move SOP DeepAgent streaming out of graph nodes while preserving SOP quality check behavior.

**Architecture:** Add generic session/message storage and APIs, then adapt SOP quality checks to reference a session. Agent/deepagent streaming becomes a runtime concern through `DeepAgentStreamRunner` and `SessionMessageWriter`; SOP graph nodes only emit user-visible step messages. Token deltas remain live-only, while final messages are persisted and replayable.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Alembic, PostgreSQL 13, LangGraph, deepagents, React 19, Vite, TypeScript, EventSource/SSE, pytest, Vitest.

---

## Reference

Design doc:

```text
docs/plans/2026-05-29-unified-agent-session-streaming-design.md
```

Key decisions:

- Use shared `sessions` and `messages` tables.
- `sessions.id` is an autoincrement bigint primary key.
- `sessions.thread_id` is the LangGraph thread ID.
- `messages.id` is UUID.
- `messages.sequence` is session-local and drives SSE `after`.
- No `user_id` in `sessions`.
- Token deltas are live-only and are not inserted into `messages`.
- SOP quality is still a graph; DeepAgent is only the `review_sop` node executor.

---

### Task 1: Add Session And Message Models

**Files:**
- Create: `app/models/sessions.py`
- Modify: `app/models/__init__.py`
- Create: `tests/test_session_models.py`

**Step 1: Write the failing model tests**

Add `tests/test_session_models.py`:

```python
from app.models.sessions import Message, Session


def test_session_model_columns() -> None:
    columns = Session.__table__.columns

    assert Session.__tablename__ == "sessions"
    assert columns["id"].primary_key
    assert columns["thread_id"].nullable is False
    assert columns["status"].nullable is False
    assert "user_id" not in columns


def test_message_model_columns() -> None:
    columns = Message.__table__.columns

    assert Message.__tablename__ == "messages"
    assert columns["id"].primary_key
    assert columns["session_id"].nullable is False
    assert columns["sequence"].nullable is False
    assert columns["role"].nullable is False
    assert columns["content"].nullable is False
    assert columns["additional_kwargs"].nullable is False


def test_message_model_indexes() -> None:
    indexes = {index.name: index for index in Message.__table__.indexes}

    assert indexes["uq_messages_session_sequence"].unique is True
    assert [
        column.name for column in indexes["uq_messages_session_sequence"].columns
    ] == ["session_id", "sequence"]
    assert [
        column.name for column in indexes["ix_messages_session_created_at"].columns
    ] == ["session_id", "created_at"]
```

**Step 2: Run the failing tests**

Run:

```bash
uv run pytest tests/test_session_models.py -q
```

Expected: FAIL because `app.models.sessions` does not exist.

**Step 3: Add the models**

Create `app/models/sessions.py`:

```python
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("uq_messages_session_sequence", "session_id", "sequence", unique=True),
        Index("ix_messages_session_created_at", "session_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    additional_kwargs: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    session: Mapped[Session] = relationship(back_populates="messages")
```

Modify `app/models/__init__.py` to import `Session` and `Message`.

**Step 4: Verify the tests pass**

Run:

```bash
uv run pytest tests/test_session_models.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/models/sessions.py app/models/__init__.py tests/test_session_models.py
git commit -m "feat: add session transcript models"
```

---

### Task 2: Add Session Migration

**Files:**
- Create: `migrations/versions/20260529_0008_create_sessions_messages.py`
- Modify: `tests/test_migrations.py`

**Step 1: Write the failing migration tests**

Extend `tests/test_migrations.py` with checks that the migration creates:

```python
def test_sessions_migration_creates_transcript_tables() -> None:
    source = MIGRATION_0008.read_text()

    assert '"sessions"' in source
    assert '"messages"' in source
    assert "thread_id" in source
    assert "additional_kwargs" in source
    assert "uq_messages_session_sequence" in source
    assert "ix_messages_session_created_at" in source
    assert "user_id" not in source
```

Use a constant:

```python
MIGRATION_0008 = Path(
    "migrations/versions/20260529_0008_create_sessions_messages.py"
)
```

**Step 2: Run the failing test**

Run:

```bash
uv run pytest tests/test_migrations.py::test_sessions_migration_creates_transcript_tables -q
```

Expected: FAIL because the migration file does not exist.

**Step 3: Add the migration**

Create `migrations/versions/20260529_0008_create_sessions_messages.py`.

Important details:

- `down_revision = "20260527_0007"`
- Create `sessions` first.
- Create `messages` second.
- Add unique index on `messages(session_id, sequence)`.
- Add index on `messages(session_id, created_at)`.

Use SQLAlchemy/Alembic style consistent with existing migrations.

**Step 4: Verify migration tests**

Run:

```bash
uv run pytest tests/test_migrations.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add migrations/versions/20260529_0008_create_sessions_messages.py tests/test_migrations.py
git commit -m "feat: create session transcript tables"
```

---

### Task 3: Add Session Schemas And Repository

**Files:**
- Create: `app/schemas/sessions.py`
- Create: `app/repositories/sessions.py`
- Modify: `app/repositories/__init__.py`
- Create: `tests/test_session_repository.py`
- Create: `tests/test_session_schemas.py`

**Step 1: Write failing repository tests**

Create tests for:

- `create_session()` creates `status="active"` and a UUID-like `thread_id`.
- `append_message()` assigns sequence 1, then 2 for the same session.
- `get_messages_after(session_id, after=1)` returns only later messages.
- `latest_sequence(session_id)` returns 0 when no messages exist.

Example:

```python
async def test_append_message_assigns_session_local_sequence(session) -> None:
    repository = SessionRepository(session)
    runtime_session = await repository.create_session()

    first = await repository.append_message(
        runtime_session.id,
        role="user",
        content="hello",
    )
    second = await repository.append_message(
        runtime_session.id,
        role="assistant",
        content="world",
    )

    assert first.sequence == 1
    assert second.sequence == 2
```

**Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/test_session_repository.py tests/test_session_schemas.py -q
```

Expected: FAIL because repository and schemas do not exist.

**Step 3: Implement schemas**

Create `app/schemas/sessions.py` with:

```python
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


SessionStatus = Literal["active", "completed", "failed", "interrupted"]
MessageRole = Literal["user", "assistant", "tool", "system"]


class SessionDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    thread_id: str
    status: SessionStatus
    title: str | None
    latest_sequence: int
    created_at: datetime
    updated_at: datetime


class SessionMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: int
    sequence: int
    role: MessageRole
    content: str
    additional_kwargs: dict[str, Any]
    created_at: datetime
```

**Step 4: Implement repository**

Create `app/repositories/sessions.py` with:

- `create_session(title: str | None = None, thread_id: str | None = None)`
- `get_session(session_id: int)`
- `get_session_by_thread_id(thread_id: str)`
- `set_status(session_id: int, status: str)`
- `append_message(session_id, role, content, additional_kwargs=None)`
- `get_messages_after(session_id, after=0, limit=100)`
- `latest_sequence(session_id)`
- `_lock_session(session_id)`

Sequence allocation must lock `sessions` before reading max sequence.

**Step 5: Verify tests**

Run:

```bash
uv run pytest tests/test_session_repository.py tests/test_session_schemas.py -q
```

Expected: PASS.

**Step 6: Commit**

```bash
git add app/schemas/sessions.py app/repositories/sessions.py app/repositories/__init__.py tests/test_session_repository.py tests/test_session_schemas.py
git commit -m "feat: add session transcript repository"
```

---

### Task 4: Add Generic Session Streaming API

**Files:**
- Create: `app/services/session_streaming.py`
- Create: `app/api/v1/sessions.py`
- Modify: `app/api/deps.py`
- Modify: `app/main.py`
- Modify: `api/openapi.yml`
- Modify: `tests/test_openapi_contract.py`
- Create: `tests/test_sessions_api.py`
- Create: `tests/test_session_stream_api.py`

**Step 1: Write failing API tests**

Cover:

- `GET /api/sessions/{session_id}` returns `latest_sequence`.
- `GET /api/sessions/{session_id}/messages?after=1` returns persisted messages.
- `GET /api/sessions/{session_id}/stream?after=1` replays messages after the cursor.
- Live delta events do not include a persisted sequence cursor.

**Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/test_sessions_api.py tests/test_session_stream_api.py -q
```

Expected: FAIL because routes do not exist.

**Step 3: Implement generic broadcaster**

Create `app/services/session_streaming.py`:

```python
import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any


class SessionBroadcast:
    def __init__(self) -> None:
        self._subscribers: dict[int, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)

    @asynccontextmanager
    async def subscribe(self, session_id: int) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers[session_id].add(queue)
        try:
            yield queue
        finally:
            self._subscribers[session_id].discard(queue)
            if not self._subscribers[session_id]:
                self._subscribers.pop(session_id, None)

    async def publish(self, session_id: int, message: dict[str, Any]) -> None:
        for queue in list(self._subscribers.get(session_id, ())):
            await queue.put(dict(message))
```

**Step 4: Implement routes**

Create `app/api/v1/sessions.py` with:

- `GET /api/sessions/{session_id}`
- `GET /api/sessions/{session_id}/messages`
- `GET /api/sessions/{session_id}/stream`

SSE formatting:

```python
def format_session_sse(event: dict[str, object]) -> str:
    data = json.dumps(event, ensure_ascii=False, default=str)
    if event.get("type") == "message":
        message = event.get("message")
        if isinstance(message, dict) and isinstance(message.get("sequence"), int):
            return f"id: {message['sequence']}\nevent: message\ndata: {data}\n\n"
    return f"event: {event.get('type', 'live')}\ndata: {data}\n\n"
```

Register the router in `app/main.py`.

**Step 5: Update OpenAPI**

Document:

- `/api/sessions/{session_id}`
- `/api/sessions/{session_id}/messages`
- `/api/sessions/{session_id}/stream`
- `SessionDetail`
- `SessionMessage`

Update `tests/test_openapi_contract.py`.

**Step 6: Verify API tests**

Run:

```bash
uv run pytest tests/test_sessions_api.py tests/test_session_stream_api.py tests/test_openapi_contract.py -q
```

Expected: PASS.

**Step 7: Commit**

```bash
git add app/services/session_streaming.py app/api/v1/sessions.py app/api/deps.py app/main.py app/schemas/sessions.py api/openapi.yml tests/test_sessions_api.py tests/test_session_stream_api.py tests/test_openapi_contract.py
git commit -m "feat: add session transcript streaming api"
```

---

### Task 5: Add Session Message Writer And DeepAgent Stream Runner

**Files:**
- Create: `app/core/agent_streaming.py`
- Create: `app/services/session_messages.py`
- Create: `tests/test_agent_streaming.py`
- Create: `tests/test_session_message_writer.py`

**Step 1: Write failing stream runner tests**

Cover:

- Runner prefers `agent.astream`.
- Runner broadcasts live `message_delta` for content chunks.
- Runner detects `reasoning_content` and emits thinking status without the text.
- Runner persists exactly one final assistant message.
- Runner falls back to `ainvoke` when no `astream` exists.

**Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/test_agent_streaming.py tests/test_session_message_writer.py -q
```

Expected: FAIL because the runtime modules do not exist.

**Step 3: Implement core runtime types**

Create `app/core/agent_streaming.py` with:

- `DeepAgentRunInput`
- `DeepAgentRunResult`
- `SessionMessageWriter` protocol
- `LiveEventPublisher` protocol/type alias
- `DeepAgentStreamRunner`

The runner should use:

```python
stream = agent.astream(payload, stream_mode=["messages", "updates", "custom"])
```

It should aggregate content deltas and call:

```python
await writer.append_step_message(
    step=step,
    role="assistant",
    content=final_text,
    additional_kwargs={"kind": "final_message", "step": step},
)
```

**Step 4: Implement repository-backed writer**

Create `app/services/session_messages.py`:

- `RepositorySessionMessageWriter`
- Inject `SessionRepository`, `SessionBroadcast | None`, and `session_id`.
- On append, call repository `append_message`.
- Publish persisted event:

```python
{"type": "message", "message": session_message_to_dict(message)}
```

Do not publish token deltas here; live deltas are owned by stream runners.

**Step 5: Verify tests**

Run:

```bash
uv run pytest tests/test_agent_streaming.py tests/test_session_message_writer.py -q
```

Expected: PASS.

**Step 6: Commit**

```bash
git add app/core/agent_streaming.py app/services/session_messages.py tests/test_agent_streaming.py tests/test_session_message_writer.py
git commit -m "feat: add deepagent session streaming runtime"
```

---

### Task 6: Link SOP Quality Checks To Sessions

**Files:**
- Modify: `app/models/sop_quality_checks.py`
- Modify: `app/repositories/sop_quality_checks.py`
- Modify: `app/services/sop_quality.py`
- Modify: `app/api/deps.py`
- Modify: `app/api/v1/sop_quality_checks.py`
- Modify: `app/schemas/sop_quality_checks.py`
- Create: `migrations/versions/20260529_0009_add_sop_quality_session_id.py`
- Modify: `tests/test_models.py`
- Modify: `tests/test_sop_quality_check_repository.py`
- Modify: `tests/test_sop_quality_service.py`
- Modify: `tests/test_sop_quality_checks_api.py`
- Modify: `tests/test_sop_quality_check_schemas.py`

**Step 1: Write failing tests**

Add expectations:

- `SopQualityCheck` has `session_id`.
- Repository `create_check` accepts `session_id` and `thread_id`.
- Service creates a session before creating a new check.
- Existing active check path does not create a new session.
- API detail returns `session_id`.

**Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/test_models.py tests/test_sop_quality_check_repository.py tests/test_sop_quality_service.py tests/test_sop_quality_checks_api.py tests/test_sop_quality_check_schemas.py -q
```

Expected: FAIL because `session_id` is missing.

**Step 3: Add migration and model field**

Migration should:

- add nullable `session_id` first
- create FK to `sessions(id)`
- include a path to backfill or document dev-only limitation
- make `session_id` not null only after backfill if required

For this PR branch, if there is no production data, a single non-null add can be
acceptable only if database tests confirm it works from a clean database.

**Step 4: Update SOP creation flow**

Update `SopQualityService` to receive `SessionRepository`.

Expected flow:

```text
if active check exists:
  return active check
create session
create sop_quality_check(session_id=session.id, thread_id=session.thread_id)
commit
schedule check
```

Preserve the partial unique index protection for races. If a race raises
`ActiveSopQualityCheckExistsError`, rollback the transaction and return the
active check.

**Step 5: Update schemas and API**

Add `session_id` to SOP detail and start response if useful for frontend
hydration. At minimum add it to `SopQualityCheckDetail`.

**Step 6: Verify tests**

Run:

```bash
uv run pytest tests/test_models.py tests/test_sop_quality_check_repository.py tests/test_sop_quality_service.py tests/test_sop_quality_checks_api.py tests/test_sop_quality_check_schemas.py -q
```

Expected: PASS.

**Step 7: Commit**

```bash
git add app/models/sop_quality_checks.py app/repositories/sop_quality_checks.py app/services/sop_quality.py app/api/deps.py app/api/v1/sop_quality_checks.py app/schemas/sop_quality_checks.py migrations/versions/20260529_0009_add_sop_quality_session_id.py tests/test_models.py tests/test_sop_quality_check_repository.py tests/test_sop_quality_service.py tests/test_sop_quality_checks_api.py tests/test_sop_quality_check_schemas.py
git commit -m "feat: link sop quality checks to sessions"
```

---

### Task 7: Refactor SOP Graph Nodes To Use The Runtime

**Files:**
- Modify: `app/agent/sop_quality/graph.py`
- Modify: `app/agent/sop_quality/nodes/load_sop.py`
- Modify: `app/agent/sop_quality/nodes/review_sop.py`
- Modify: `app/agent/sop_quality/nodes/summarize_result.py`
- Modify: `app/agent/sop_quality/nodes/submit_result.py`
- Modify: `app/services/sop_quality_runner.py`
- Modify: `tests/test_sop_quality_graph.py`
- Modify: `tests/test_sop_quality_runner.py`

**Step 1: Write failing graph tests**

Tests should prove:

- `review_sop` uses a `DeepAgentStreamRunner` dependency.
- `review_sop.py` no longer imports `runtime_stream_event`.
- A fake runner returning `DeepAgentRunResult(final_text="...")` feeds `review_output`.
- Ordinary nodes call `append_step_message` for user-visible step output.
- Token deltas are not written by ordinary nodes.

**Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/test_sop_quality_graph.py tests/test_sop_quality_runner.py -q
```

Expected: FAIL until the graph dependencies are refactored.

**Step 3: Update graph construction**

`build_sop_quality_graph(...)` should accept:

- `message_writer`
- `deepagent_stream_runner`
- `live_event_publisher` or `session_broadcast`

Keep no-op defaults for unit tests that do not care about transcript writes.

**Step 4: Refactor `review_sop`**

The node should:

```python
agent = await create_deepagents(...)
result = await deepagent_stream_runner.run_step(
    agent=agent,
    step="review_sop",
    input=DeepAgentRunInput(messages=[_user_message(state)]),
)
return {"review_output": result.final_text}
```

It should not parse `astream` chunks.

**Step 5: Refactor ordinary nodes**

Only append user-visible step transcript:

- `load_sop`: SOP loaded summary, not the full SOP snapshot.
- `summarize_result`: report markdown or summary.
- `submit_result`: external submission summary.

**Step 6: Update runner wiring**

`run_sop_quality_check` should:

- load the check and its `session_id`
- construct `SessionRepository`
- construct `RepositorySessionMessageWriter`
- construct `DeepAgentStreamRunner`
- pass them to the graph
- keep setting `current_checkpoint_id`
- keep business status/result updates in `sop_quality_checks`

**Step 7: Verify graph tests**

Run:

```bash
uv run pytest tests/test_sop_quality_graph.py tests/test_sop_quality_runner.py -q
```

Expected: PASS.

**Step 8: Commit**

```bash
git add app/agent/sop_quality/graph.py app/agent/sop_quality/nodes/load_sop.py app/agent/sop_quality/nodes/review_sop.py app/agent/sop_quality/nodes/summarize_result.py app/agent/sop_quality/nodes/submit_result.py app/services/sop_quality_runner.py tests/test_sop_quality_graph.py tests/test_sop_quality_runner.py
git commit -m "refactor: route sop graph output through sessions"
```

---

### Task 8: Bridge SOP Stream Compatibility To Session Messages

**Files:**
- Modify: `app/api/v1/sop_quality_checks.py`
- Modify: `app/agent/sop_quality/display.py`
- Modify: `tests/test_sop_quality_check_stream_api.py`
- Modify: `tests/test_sop_quality_display.py`

**Step 1: Write failing compatibility tests**

Tests should prove:

- Existing `GET /api/sop-quality-checks/{check_id}/stream?after=N` still works.
- The route can replay session messages for the check's `session_id`.
- Persisted session message events advance cursor.
- Live token deltas do not advance cursor.
- Display state can be built from session messages grouped by step.

**Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/test_sop_quality_check_stream_api.py tests/test_sop_quality_display.py -q
```

Expected: FAIL until the route uses session messages.

**Step 3: Implement compatibility mapping**

Short-term options:

- Keep SOP stream path and internally query `check.session_id`.
- Replay session messages as SOP-compatible events if the existing frontend still
  expects SOP event shape.
- Prefer adding `session_id` to the frontend and moving it to the generic session
  hook in Task 9.

Do not write new long-term data to `sop_quality_events` unless compatibility
requires it for old paths.

**Step 4: Verify compatibility tests**

Run:

```bash
uv run pytest tests/test_sop_quality_check_stream_api.py tests/test_sop_quality_display.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/api/v1/sop_quality_checks.py app/agent/sop_quality/display.py tests/test_sop_quality_check_stream_api.py tests/test_sop_quality_display.py
git commit -m "refactor: bridge sop streams to session transcript"
```

---

### Task 9: Add Frontend Session Stream Hook And SOP Projection

**Files:**
- Create: `frontend/src/features/sessions/types.ts`
- Create: `frontend/src/features/sessions/api.ts`
- Create: `frontend/src/features/sessions/reducer.ts`
- Create: `frontend/src/features/sessions/hooks.ts`
- Create: `frontend/src/features/sessions/api.test.ts`
- Create: `frontend/src/features/sessions/reducer.test.ts`
- Create: `frontend/src/features/sessions/hooks.test.tsx`
- Modify: `frontend/src/features/sop-quality-checks/types.ts`
- Modify: `frontend/src/features/sop-quality-checks/reducer.ts`
- Modify: `frontend/src/features/sop-quality-checks/hooks.ts`
- Modify: `frontend/src/features/sop-quality-checks/reducer.test.ts`
- Modify: `frontend/src/features/sop-quality-checks/hooks.test.tsx`

**Step 1: Write failing frontend tests**

Cover:

- `buildSessionStreamUrl(sessionId, after)` returns `/api/sessions/{id}/stream?after=N`.
- Persisted `message` events update `latestSequence`.
- Live `message_delta` events do not update `latestSequence`.
- Live assistant delta is buffered by step/turn.
- SOP projection groups messages by `additional_kwargs.step`.
- Thinking live event changes thinking state without showing reasoning text.

**Step 2: Run failing frontend tests**

Run:

```bash
cd frontend && npm run test -- sessions sop-quality-checks
```

Expected: FAIL because session feature files do not exist.

**Step 3: Implement session feature**

Create a generic reducer state:

```ts
type SessionViewState = {
  latestSequence: number;
  messages: SessionMessage[];
  liveBuffers: Record<string, string>;
  connectionStatus: "idle" | "connecting" | "open" | "reconnecting" | "closed";
};
```

Use keys like `step:<step>` or `turn:<turn_id>` for live buffers.

**Step 4: Adapt SOP hook**

SOP detail should use `session_id` when available. It can call
`useSessionStream(sessionId)` and project messages into existing SOP node state.

Keep a fallback to the old SOP stream path only if old checks can lack
`session_id`.

**Step 5: Verify frontend tests**

Run:

```bash
cd frontend && npm run test -- sessions sop-quality-checks
```

Expected: PASS.

**Step 6: Commit**

```bash
git add frontend/src/features/sessions frontend/src/features/sop-quality-checks
git commit -m "feat: add shared session stream frontend state"
```

---

### Task 10: Update Contracts And Documentation

**Files:**
- Modify: `api/openapi.yml`
- Modify: `docs/frontend.md`
- Modify: `docs/llm-provider-capabilities.md`
- Modify: `docs/plans/2026-05-29-unified-agent-session-streaming-design.md` if implementation decisions changed
- Modify: `tests/test_openapi_contract.py`

**Step 1: Write or update failing contract tests**

Ensure OpenAPI documents:

- session APIs
- `SessionDetail`
- `SessionMessage`
- `session_id` on SOP quality detail
- no reintroduced generic `/api/runs` paths

**Step 2: Run contract tests**

Run:

```bash
uv run pytest tests/test_openapi_contract.py -q
```

Expected: FAIL until OpenAPI is updated.

**Step 3: Update docs**

Document:

- token deltas are live-only
- persisted transcript lives in `messages`
- SOP graph node outputs are grouped by `additional_kwargs.step`
- DeepAgent is explicit in the SOP review node/runtime
- future agent playground will reuse `sessions/messages`

**Step 4: Verify docs and contracts**

Run:

```bash
uv run pytest tests/test_openapi_contract.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add api/openapi.yml docs/frontend.md docs/llm-provider-capabilities.md docs/plans/2026-05-29-unified-agent-session-streaming-design.md tests/test_openapi_contract.py
git commit -m "docs: document shared session streaming contract"
```

---

### Task 11: Full Verification

**Files:**
- No planned source edits unless verification exposes a defect.

**Step 1: Run backend tests**

Run:

```bash
uv run pytest -q
```

Expected: PASS.

**Step 2: Run database tests if PostgreSQL test database is available**

Run with the local test DB URL:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5543/change_quality_agent_test_20260528144035 uv run pytest -m db
```

Expected: PASS or report that the configured database is unavailable.

**Step 3: Run frontend tests**

Run:

```bash
cd frontend && npm run test
```

Expected: PASS.

**Step 4: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

**Step 5: Inspect for legacy run path regressions**

Run:

```bash
rg -n "run_events|/api/runs|test-runs|runs" app frontend api docs tests
```

Expected:

- No backend/frontend route usage for old generic runs.
- Only explicit negative tests or historical design references are allowed.

**Step 6: Commit fixes if needed**

If verification required fixes:

```bash
git add <fixed files>
git commit -m "fix: stabilize unified session streaming"
```

**Step 7: Push branch**

After all commits are complete:

```bash
git push origin codex/sop-quality-checkpoint-impl
```

