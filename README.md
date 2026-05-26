# Change Quality Agent

Change Quality Agent provides the backend substrate for running SOP quality
checks, managing ReAct agent definitions, and observing long-running work.

## Capabilities

- Starts SOP quality runs from a mocked SOP source in v1.
- Manages draft and published ReAct agent definitions for dynamically created
  agent nodes.
- Starts ReAct agent test runs through the shared run and event substrate.
- Persists run history and durable run events in Postgres.
- Exposes generic run observation so clients can inspect status without
  depending on subject-specific fields.
- Streams persisted run events for replay and progress observation.
- Manages MCP server configuration and stdio runtime lifecycle behind the
  `X-MCP-Admin-Token` header. Set `mcp_admin_token`, allow commands with
  `mcp_allowed_stdio_commands`, pin launchable command/first-arg pairs with
  `mcp_allowed_stdio_specs` such as `uvx:mcp-server-filesystem`, and only set
  `mcp_runtime_single_instance=true` when the API is deployed as a single
  process owning MCP child processes.
- Uses in-process v1 runners while worker leases, checkpoint resume, tool/MCP
  resolution, LLM provider UI, and the real SOP client remain future integration
  points.

## Full-Stack SOP Debugging

Use Postgres 13 for local end-to-end SOP run debugging.

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

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/change_quality_agent \
  uv run fastapi dev --host 127.0.0.1 --port 8000

cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```
