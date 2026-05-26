# Logging Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add dependency-free application logging and FastAPI request access logging.

**Architecture:** Use Python standard-library `logging` configured through a new `app/core/logging.py` boundary. Extend existing `Settings` with logging fields and register lightweight request logging middleware in `app/main.py`.

**Tech Stack:** Python 3.12, FastAPI, Pydantic Settings, pytest, httpx ASGITransport, standard-library `logging`.

---

## Required Skills

Use these skills while executing this plan:

- @superpowers:test-driven-development for each behavior change.
- @fastapi when touching `app/main.py` middleware behavior.
- @project-structure when placing config, core logging, and tests.
- @superpowers:verification-before-completion before claiming completion.

## Branch And Workspace

Run all commands from the existing worktree:

```bash
cd /Users/wanyaozhong/Projects/change-quality-agent/.worktrees/logging-design
```

Do not make changes in `/Users/wanyaozhong/Projects/change-quality-agent` because that path is on `main`.

## Task 1: Add Logging Settings

**Files:**
- Modify: `app/core/config.py`
- Modify: `tests/test_config.py`

**Step 1: Write failing tests**

Add tests to `tests/test_config.py`:

```python
def test_logging_settings_have_defaults() -> None:
    settings = Settings()

    assert settings.log_level == "INFO"
    assert settings.access_log_enabled is True


def test_logging_settings_can_be_overridden_by_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ACCESS_LOG_ENABLED", "false")

    settings = Settings()

    assert settings.log_level == "DEBUG"
    assert settings.access_log_enabled is False
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_config.py::test_logging_settings_have_defaults tests/test_config.py::test_logging_settings_can_be_overridden_by_environment -v
```

Expected: FAIL because `Settings` has no `log_level` or `access_log_enabled` fields.

**Step 3: Implement minimal settings fields**

In `app/core/config.py`, add fields to `Settings`:

```python
    log_level: str = "INFO"
    access_log_enabled: bool = True
```

Do not add validators yet unless a test requires them. Keep this change small.

**Step 4: Run tests to verify pass**

Run:

```bash
uv run pytest tests/test_config.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/core/config.py tests/test_config.py
git commit -m "feat: add logging settings"
```

## Task 2: Add Logging Configuration Module

**Files:**
- Create: `app/core/logging.py`
- Create: `tests/test_logging.py`

**Step 1: Write failing tests**

Create `tests/test_logging.py`:

```python
import logging

import pytest

from app.core.config import Settings
from app.core.logging import configure_logging


def test_configure_logging_sets_root_level() -> None:
    configure_logging(Settings(log_level="DEBUG"))

    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_rejects_invalid_level() -> None:
    with pytest.raises(ValueError, match="Invalid log level"):
        configure_logging(Settings(log_level="NOPE"))
```

**Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_logging.py -v
```

Expected: FAIL because `app.core.logging` does not exist.

**Step 3: Implement minimal logging module**

Create `app/core/logging.py`:

```python
import logging
import logging.config

from app.core.config import Settings


def configure_logging(settings: Settings) -> None:
    level_name = settings.log_level.upper()
    level = logging.getLevelName(level_name)
    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {settings.log_level}")

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
            },
            "root": {
                "handlers": ["console"],
                "level": level_name,
            },
        }
    )
```

**Step 4: Run tests to verify pass**

Run:

```bash
uv run pytest tests/test_logging.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/core/logging.py tests/test_logging.py
git commit -m "feat: configure application logging"
```

## Task 3: Register Logging Configuration

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_logging.py`

**Step 1: Write failing test**

Add a test that verifies app import configures logging at the default level. Because `app.main` may already be imported by other tests, keep this test focused on the `configure_logging` boundary if module reload becomes brittle. Prefer not to over-test import side effects.

Recommended test in `tests/test_logging.py`:

```python
def test_configure_logging_keeps_existing_library_loggers_enabled() -> None:
    configure_logging(Settings(log_level="INFO"))

    assert logging.getLogger("uvicorn.error").disabled is False
```

**Step 2: Run test to verify current behavior**

Run:

```bash
uv run pytest tests/test_logging.py::test_configure_logging_keeps_existing_library_loggers_enabled -v
```

Expected: PASS if Task 2 used `disable_existing_loggers=False`. If it fails, fix Task 2 before continuing.

**Step 3: Register logging in app startup module**

Modify `app/main.py`:

```python
from app.core.config import settings
from app.core.logging import configure_logging

configure_logging(settings)
```

Place the call before creating `FastAPI(...)` so app logging is configured before lifespan and router behavior runs.

**Step 4: Run app tests**

Run:

```bash
uv run pytest tests/test_app.py tests/test_startup_cleanup.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/main.py tests/test_logging.py
git commit -m "feat: initialize logging for app"
```

## Task 4: Add Access Logging Middleware

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_app.py`

**Step 1: Write successful request logging test**

Add to `tests/test_app.py`:

```python
import logging

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_access_log_records_successful_request(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="app.access")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert any(
        "GET /health 200" in record.message and "duration_ms=" in record.message
        for record in caplog.records
    )
```

Keep imports DRY with the existing file imports. Do not duplicate imports already present.

**Step 2: Run test to verify failure**

Run:

```bash
uv run pytest tests/test_app.py::test_access_log_records_successful_request -v
```

Expected: FAIL because no access middleware logs the request.

**Step 3: Implement middleware**

Modify `app/main.py`:

```python
import logging
from time import perf_counter

from fastapi import FastAPI, Request

access_logger = logging.getLogger("app.access")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    if not settings.access_log_enabled:
        return await call_next(request)

    started_at = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (perf_counter() - started_at) * 1000
        access_logger.exception(
            "%s %s failed duration_ms=%.2f",
            request.method,
            request.url.path,
            duration_ms,
        )
        raise

    duration_ms = (perf_counter() - started_at) * 1000
    access_logger.info(
        "%s %s %s duration_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response
```

Use the exact existing app object; do not create a second `FastAPI` instance.

**Step 4: Run test to verify pass**

Run:

```bash
uv run pytest tests/test_app.py::test_access_log_records_successful_request -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add app/main.py tests/test_app.py
git commit -m "feat: log HTTP requests"
```

## Task 5: Cover Access Logging Edge Cases

**Files:**
- Modify: `app/main.py` if needed
- Modify: `tests/test_app.py`

**Step 1: Write disabled access log test**

Because `settings` is imported as a module-level singleton, use `monkeypatch` to update the existing object for this test and restore automatically:

```python
@pytest.mark.asyncio
async def test_access_log_can_be_disabled(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "access_log_enabled", False)
    caplog.set_level(logging.INFO, logger="app.access")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert not [record for record in caplog.records if record.name == "app.access"]
```

**Step 2: Write exception logging test**

Add a temporary route for the test only:

```python
@pytest.mark.asyncio
async def test_access_log_records_request_exceptions(
    caplog: pytest.LogCaptureFixture,
) -> None:
    @app.get("/__test_error")
    async def test_error() -> None:
        raise RuntimeError("boom")

    caplog.set_level(logging.ERROR, logger="app.access")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/__test_error")

    assert response.status_code == 500
    assert any(
        "GET /__test_error failed" in record.message
        and "duration_ms=" in record.message
        for record in caplog.records
    )
```

If duplicate route registration creates test pollution, move this case to a local `FastAPI` test app using the same middleware helper. Prefer extracting a middleware function only if needed by the test; do not over-abstract first.

**Step 3: Run tests to verify behavior**

Run:

```bash
uv run pytest tests/test_app.py::test_access_log_can_be_disabled tests/test_app.py::test_access_log_records_request_exceptions -v
```

Expected: PASS after Task 4 implementation, or FAIL with a clear middleware bug to fix.

**Step 4: Make minimal fixes if needed**

Only change `app/main.py` if the tests reveal an issue. Keep the middleware simple and avoid adding request IDs or structured fields in this change.

**Step 5: Commit**

```bash
git add app/main.py tests/test_app.py
git commit -m "test: cover access logging behavior"
```

If no implementation changed in this task, the commit message may still be test-focused.

## Task 6: Final Verification

**Files:**
- No planned file changes.

**Step 1: Run full test suite**

Run:

```bash
uv run pytest
```

Expected: `38+ passed`, existing DB-marked tests may remain skipped unless local Postgres test settings are configured.

**Step 2: Inspect diff**

Run:

```bash
git status --short
git log --oneline --decorate -6
git diff main...HEAD -- app tests docs/plans
```

Expected:

- Working tree is clean.
- Commits are small and task-oriented.
- Diff only touches logging design/plan docs, config, logging module, app main, and tests.

**Step 3: Manual smoke test**

Run:

```bash
uv run fastapi dev
```

In another terminal, run:

```bash
curl -s http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

Expected server log contains a line similar to:

```text
INFO [app.access] GET /health 200 duration_ms=...
```

Stop the server after the smoke test.

**Step 4: Final commit if needed**

If verification required any cleanup changes, commit them:

```bash
git add <changed-files>
git commit -m "chore: verify logging setup"
```

If no files changed, do not create an empty commit.
