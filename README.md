# Change Quality Agent

Change Quality Agent provides the backend substrate for running SOP quality
checks, managing agent definitions, and observing SOP quality check progress.

## Capabilities

- Starts or joins global SOP quality checks from a mocked SOP source in v1.
- Manages draft and published ReAct agent definitions for dynamically created
  agent nodes.
- Persists SOP quality check history and lightweight lifecycle events in
  Postgres.
- Stores graph state, messages, and resume data in LangGraph Postgres
  checkpoints.
- Streams SOP quality check lifecycle events for reconnectable progress
  observation.
- Manages MCP server configuration and stdio runtime lifecycle for admin users.
  Allow commands with `mcp_allowed_stdio_commands`, pin launchable
  command/first-arg pairs with `mcp_allowed_stdio_specs` such as
  `uvx:mcp-server-filesystem`, and only set `mcp_runtime_single_instance=true`
  when the API is deployed as a single process owning MCP child processes.
- Runs `codeagent:<model>` agent versions through the internal CodeAgent-compatible
  model factory. Configure `CODEAGENT_BASE_URL` and
  `CODEAGENT_TOKEN_PROVIDER=codeagent` on the API process; token headers are
  refreshed before each model HTTP request by the CodeAgent token provider.
- Uses in-process v1 check runners while worker leases, checkpoint resume, tool/MCP
  resolution, LLM provider UI, and the real SOP client remain future integration
  points.

## SOP Quality Check API

`POST /api/sop-quality-checks?sop_id=<sop_id>&env=<env_key>` starts a new
check or joins the active check for the same SOP and environment. New checks
return `202` with `created: true`; joined active checks return `200` with
`created: false`.

Clients observe progress through the stream endpoint:
`GET /api/sop-quality-checks/{check_id}/stream?after=<sequence>`. The API also
exposes `GET /api/sop-quality-checks/{check_id}` for the current business
snapshot and `GET /api/sop-quality-checks/{check_id}/events?after=<sequence>`
for lightweight reconnect replay.

LangGraph Postgres checkpoints are the durable source for graph state,
messages, and resume data. The `sop_quality_events` table intentionally stores
only lightweight SSE cursors: sequence, event type, node, checkpoint id, task
id, message, and timestamp.

## Full-Stack SOP Debugging

Use Postgres 13 for local end-to-end SOP quality check debugging.

Database and migrations:

```bash
docker run -d --name cqa-postgres-13 \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=change_quality_agent \
  -p 5432:5432 \
  postgres:13

until docker exec cqa-postgres-13 pg_isready \
  -U postgres \
  -d change_quality_agent; do
  sleep 1
done

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/change_quality_agent \
  uv run alembic upgrade head
```

Backend terminal:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/change_quality_agent \
  make dev
```

Frontend terminal:

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```
