# Change Quality Agent

## 本地 Skill 准备

本仓库不再提交 `.agents/` 目录中的 skill 实现；该目录只作为本地 agent/Codex 环境配置使用。

开始开发或运行 agent 前，请先在本机增加项目需要的 skills，再进行代码改动。当前项目至少需要关注：

- `using-git-worktrees`
- `fastapi`
- `project-structure`

如果参与前端相关工作，请按任务需要补充 React/Vercel/Web UI 相关 skills。缺失的 skill 请从团队共享来源或个人 skill 库安装到本地环境，避免把 `.agents/` 或 `skills-lock.json` 提交到仓库。

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

The shared API contract lives in `api/sop-runs.md`. The v1 in-process runner is
intended for a single active API worker; worker leases and checkpoint resume are
deferred until the real runner is introduced.
