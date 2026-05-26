# Logging Design

## Context

The backend currently has no application-owned logging configuration. FastAPI,
Uvicorn, SQLAlchemy, and pytest all integrate naturally with Python's standard
`logging` package, so the first logging step should stay dependency-free and
compatible with the existing ecosystem.

This design covers two capabilities:

- Basic application logging configuration.
- HTTP request access logs for FastAPI requests.

Structured JSON logging, OpenTelemetry export, and third-party logging APIs are
out of scope for this change. If production observability later needs structured
fields, `structlog` is the preferred upgrade path because it can layer on top of
standard `logging` without replacing the ecosystem default.

## Goals

- Configure application logging once during FastAPI startup/import.
- Let modules use `logging.getLogger(__name__)` consistently.
- Make log level configurable through the existing `Settings` mechanism.
- Record request method, path, status code, and duration for successful requests.
- Record request method, path, and duration when request handling raises an
  exception, without swallowing the exception.
- Keep the implementation small, dependency-free, and easy to test.

## Non-Goals

- JSON or structured log output.
- Request IDs, trace IDs, or correlation IDs.
- External log shipping.
- Replacing Uvicorn's own access logger.
- Broad business-logic logging throughout the codebase.

## Proposed Approach

Add an `app/core/logging.py` module with a single public function:

```python
configure_logging(settings: Settings) -> None
```

The function will use `logging.config.dictConfig` to configure console logging
with a simple human-readable format:

```text
%(asctime)s %(levelname)s [%(name)s] %(message)s
```

`Settings` will gain two fields:

```python
log_level: str = "INFO"
access_log_enabled: bool = True
```

The existing settings source order will continue to apply, so values can come
from constructor arguments, environment variables, `config.yaml`, dotenv files,
or file secrets. Examples:

```bash
LOG_LEVEL=DEBUG
ACCESS_LOG_ENABLED=false
```

FastAPI request logging will be implemented as lightweight middleware in
`app/main.py`. The middleware will:

- Skip logging when `settings.access_log_enabled` is false.
- Measure elapsed time with a monotonic clock.
- Log successful responses through `logging.getLogger("app.access")`.
- Log exceptions with `logger.exception(...)` and re-raise the original
  exception so FastAPI's normal error behavior remains intact.

## Components

### `app/core/config.py`

Owns the new settings fields because configuration is centralized there by the
project structure rules.

### `app/core/logging.py`

Owns logging setup. Keeping this separate avoids turning `app/main.py` into a
configuration dumping ground and gives tests a direct unit boundary.

### `app/main.py`

Calls `configure_logging(settings)` near app construction and registers the
request logging middleware. This is the compliant location for FastAPI app
creation, lifespan, middleware, and router registration.

### Tests

Tests should cover:

- Default logging settings.
- Environment variable overrides for `log_level` and `access_log_enabled`.
- Request logging for successful responses.
- Exception logging for failed responses without swallowing the exception.
- Disabled access logging.

## Data Flow

1. `settings = Settings()` loads configuration using the existing source order.
2. `app/main.py` calls `configure_logging(settings)`.
3. Application modules obtain named loggers with `logging.getLogger(__name__)`.
4. The request middleware measures each HTTP request.
5. The middleware emits one access log entry for each enabled request path.

## Error Handling

Logging setup should fail fast if an invalid log level is configured. A startup
failure is preferable to silently running with an unexpected logging state.

The request middleware should never convert exceptions into responses. It logs
request context and then re-raises, preserving FastAPI and test behavior.

## Testing Strategy

Use pytest's `caplog` fixture for logging assertions. For middleware behavior,
use the existing ASGI test style with `httpx.ASGITransport`.

Run the full test suite after implementation:

```bash
uv run pytest
```

## Future Extension

If plain text logs become insufficient, add `structlog` in a later change and
keep the current public logging setup boundary. That follow-up can add JSON
rendering, request IDs, run IDs, and trace correlation without changing most
call sites.
