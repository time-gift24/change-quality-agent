# Change Quality Agent

## Development

```bash
uv sync
uv run alembic upgrade head
uv run fastapi dev
```

Repository integration tests require a local Postgres database:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/change_quality_agent_test uv run pytest tests/test_run_repository.py -v
```

## SOP Run APIs

```text
GET  /api/sop/environments
GET  /api/sop/{sop_id}?env=dev
POST /api/sop/{sop_id}/runs?env=dev
GET  /api/sop/{sop_id}/runs?env=dev
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/events?after=0
```

SOP fetching is mocked in v1. The real SOP client will be added behind the
existing `SopClient` interface later.
