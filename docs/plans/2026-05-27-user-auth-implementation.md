# User Auth Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a simple persisted user module, enforce authenticated API access, seed `common` and `admin` users for `make dev`, and show a frontend dev user picker before entering the app.

**Architecture:** Store users in Postgres through a small SQLAlchemy model and repository. Add FastAPI auth endpoints plus an HTTP middleware that resolves the current user from a dev cookie and writes a lightweight current-user object to `request.state`. In the frontend, add an auth bootstrap around the existing app shell and derive route authorization from the returned user.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic, Vite, React 19, TypeScript, Tailwind CSS v4, Vitest.

---

### Task 1: Add User Model And Migration

**Files:**
- Create: `app/models/users.py`
- Modify: `app/models/__init__.py`
- Create: `migrations/versions/20260527_0004_create_users.py`
- Modify: `tests/test_models.py`
- Modify: `tests/test_migrations.py`

**Step 1: Write failing model and migration tests**

Add tests like:

```python
from app.models.users import User


def test_user_model_table_name() -> None:
    assert User.__tablename__ == "users"


def test_user_model_has_expected_columns() -> None:
    columns = User.__table__.columns

    assert "account" in columns
    assert "refresh_token" in columns
    assert "is_admin" in columns
    assert "meta" in columns
```

Update the migration head assertion:

```python
assert heads == {"20260527_0004"}
```

**Step 2: Run tests to verify failure**

Run: `uv run pytest tests/test_models.py tests/test_migrations.py -v`

Expected: FAIL because `app.models.users` and the new migration do not exist.

**Step 3: Implement the model and migration**

Create `app/models/users.py` using the existing SQLAlchemy style:

```python
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index("uq_users_account", "account", unique=True),)

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    account: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
```

Export `User` from `app/models/__init__.py`.

Create the Alembic revision with `down_revision = "20260526_0003"` and a
matching `users` table/index. Downgrade should drop `uq_users_account`, then
drop `users`.

**Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_models.py tests/test_migrations.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add app/models/users.py app/models/__init__.py migrations/versions/20260527_0004_create_users.py tests/test_models.py tests/test_migrations.py
git commit -m "Add user persistence model"
```

---

### Task 2: Add User Repository And Dev Seeding

**Files:**
- Create: `app/repositories/users.py`
- Create: `tests/test_user_repository.py`

**Step 1: Write failing repository tests**

Add module API tests and database-backed tests following `tests/test_agent_repository.py`:

```python
def test_user_repository_module_defines_expected_public_api() -> None:
    from app.repositories import users

    assert users.UserRepository is not None
    assert users.DEV_USERS is not None
    assert users.seed_dev_users is not None
```

For `TEST_DATABASE_URL` integration tests:

```python
async def test_upsert_user_creates_and_updates_user(session) -> None:
    repository = UserRepository(session)

    created = await repository.upsert_user(
        account="common",
        refresh_token="token-1",
        is_admin=False,
        meta={"source": "test"},
    )
    updated = await repository.upsert_user(
        account="common",
        refresh_token="token-2",
        is_admin=True,
        meta={"source": "updated"},
    )

    assert created.id == updated.id
    assert updated.refresh_token == "token-2"
    assert updated.is_admin is True
```

**Step 2: Run tests to verify failure**

Run: `uv run pytest tests/test_user_repository.py -v`

Expected: FAIL because `app.repositories.users` is missing.

**Step 3: Implement repository and seed helper**

Create a minimal repository:

```python
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.users import User

DEV_USERS = (
    {
        "account": "common",
        "refresh_token": "dev-common-refresh-token",
        "is_admin": False,
        "meta": {"source": "dev"},
    },
    {
        "account": "admin",
        "refresh_token": "dev-admin-refresh-token",
        "is_admin": True,
        "meta": {"source": "dev"},
    },
)


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_account(self, account: str) -> User | None:
        statement = select(User).where(User.account == account).limit(1)
        return await self._session.scalar(statement)

    async def upsert_user(
        self,
        *,
        account: str,
        refresh_token: str,
        is_admin: bool,
        meta: dict[str, Any],
    ) -> User:
        user = await self.get_by_account(account)
        if user is None:
            user = User(
                account=account,
                refresh_token=refresh_token,
                is_admin=is_admin,
                meta=meta,
            )
            self._session.add(user)
        else:
            user.refresh_token = refresh_token
            user.is_admin = is_admin
            user.meta = meta
        await self._session.flush()
        return user


async def seed_dev_users(repository: UserRepository) -> None:
    for user in DEV_USERS:
        await repository.upsert_user(**user)
```

**Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_user_repository.py -v`

Expected: PASS, with database integration tests skipped if `TEST_DATABASE_URL`
is not configured.

**Step 5: Commit**

```bash
git add app/repositories/users.py tests/test_user_repository.py
git commit -m "Add user repository and dev seeds"
```

---

### Task 3: Add Auth Schemas, Dependencies, And Endpoints

**Files:**
- Create: `app/schemas/users.py`
- Create: `app/api/v1/auth.py`
- Modify: `app/api/v1/__init__.py`
- Modify: `app/api/deps.py`
- Modify: `app/main.py`
- Modify: `app/core/config.py`
- Modify: `tests/test_config.py`
- Create: `tests/test_auth_api.py`

**Step 1: Write failing tests**

Add settings tests:

```python
def test_auth_settings_have_defaults() -> None:
    settings = Settings()

    assert settings.auth_enabled is True
    assert settings.auth_dev_mode is False
    assert settings.auth_session_cookie_name == "cqa_user"
```

Add API tests using dependency overrides. The first assertions should be:

```python
async def test_dev_login_sets_cookie_when_dev_mode_enabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_dev_mode", True)
    # Override UserRepositoryDep with a fake repository containing common/admin.
    # POST /api/auth/dev-login should return 200 and set the configured cookie.
```

**Step 2: Run tests to verify failure**

Run: `uv run pytest tests/test_config.py tests/test_auth_api.py -v`

Expected: FAIL because auth settings and `/api/auth` routes are missing.

**Step 3: Implement schemas and dependencies**

Create `app/schemas/users.py`:

```python
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class UserPublic(BaseModel):
    id: UUID
    account: str
    is_admin: bool
    meta: dict[str, Any] = Field(default_factory=dict)


class DevLoginRequest(BaseModel):
    account: str
```

Add settings to `Settings`:

```python
auth_enabled: bool = True
auth_dev_mode: bool = False
auth_session_cookie_name: str = "cqa_user"
```

Add a `UserRepositoryDep` in `app/api/deps.py`.

**Step 4: Implement auth routes**

Create `app/api/v1/auth.py` with:

- `GET /api/auth/me`: returns `UserPublic` from `request.state.current_user`
  or raises 401.
- `POST /api/auth/dev-login`: only allowed when `settings.auth_dev_mode` is
  true; looks up `common` or `admin`; sets the configured HTTP-only cookie.
- `POST /api/auth/logout`: clears the configured cookie.

Keep `refresh_token` internal; never return it.

Include the router from `app/main.py`:

```python
from app.api.v1 import agents, auth, mcp, runs, sop

app.include_router(auth.router)
```

**Step 5: Run tests to verify pass**

Run: `uv run pytest tests/test_config.py tests/test_auth_api.py tests/test_api_dependencies.py -v`

Expected: PASS.

**Step 6: Commit**

```bash
git add app/schemas/users.py app/api/v1/auth.py app/api/v1/__init__.py app/api/deps.py app/main.py app/core/config.py tests/test_config.py tests/test_auth_api.py tests/test_api_dependencies.py
git commit -m "Add auth API endpoints"
```

---

### Task 4: Add Auth Middleware And Dev Startup Seeding

**Files:**
- Create: `app/core/security.py`
- Modify: `app/main.py`
- Create: `tests/conftest.py`
- Create: `tests/test_auth_middleware.py`
- Modify: `tests/test_startup_cleanup.py`

**Step 1: Write failing middleware tests**

Create tests that enable auth only inside the test:

```python
async def test_api_request_without_user_returns_401(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_dev_mode", True)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/sop/environments")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}
```

Add tests for bypass paths:

```python
async def test_health_bypasses_auth(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_enabled", True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
```

Add a test with a fake resolver so middleware can set `request.state.current_user`
without requiring a real database.

**Step 2: Add a test default that keeps legacy API tests focused**

Create `tests/conftest.py`:

```python
import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def disable_auth_by_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_enabled", False)
```

Auth-specific tests should set `settings.auth_enabled = True`.

**Step 3: Run tests to verify failure**

Run: `uv run pytest tests/test_auth_middleware.py tests/test_sop_api.py -v`

Expected: FAIL until middleware exists; existing SOP tests should remain stable
because auth is disabled by the autouse fixture.

**Step 4: Implement `app/core/security.py`**

Add a lightweight current-user type and helpers:

```python
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import Request


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    account: str
    is_admin: bool
    meta: dict[str, Any]


AUTH_REQUIRED_DETAIL = "Authentication required."


def is_auth_bypass_path(path: str) -> bool:
    return (
        path == "/health"
        or path in {"/docs", "/redoc", "/openapi.json"}
        or path in {"/api/auth/dev-login", "/api/auth/logout"}
    )
```

Add `resolve_current_user(request)` that reads the configured cookie in dev mode,
loads the user via `async_session` and `UserRepository`, and returns `CurrentUser`
or `None`.

**Step 5: Wire middleware and startup seed**

In `app/main.py`:

- Add middleware before request logging or immediately after app creation.
- If `settings.auth_enabled` is false or path bypasses auth, call next.
- If the path starts with `/api/` and no user resolves, return
  `JSONResponse(status_code=401, content={"detail": AUTH_REQUIRED_DETAIL})`.
- Store `request.state.current_user = current_user`.
- In lifespan, if `settings.auth_dev_mode`, seed dev users after DB startup
  cleanup and before MCP runtime startup.

**Step 6: Run tests to verify pass**

Run: `uv run pytest tests/test_auth_middleware.py tests/test_startup_cleanup.py tests/test_sop_api.py tests/test_mcp_api.py -v`

Expected: PASS.

**Step 7: Commit**

```bash
git add app/core/security.py app/main.py tests/conftest.py tests/test_auth_middleware.py tests/test_startup_cleanup.py
git commit -m "Enforce API auth middleware"
```

---

### Task 5: Add Frontend Auth Client And Context

**Files:**
- Create: `frontend/src/features/auth/types.ts`
- Create: `frontend/src/features/auth/api.ts`
- Create: `frontend/src/features/auth/AuthContext.tsx`
- Create: `frontend/src/features/auth/api.test.ts`
- Create: `frontend/src/features/auth/AuthContext.test.tsx`
- Modify: `frontend/src/lib/apiClient.ts`
- Modify: `frontend/src/lib/apiClient.test.ts`

**Step 1: Write failing frontend tests**

Test the auth API functions:

```ts
it("posts selected dev account", async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ account: "admin", is_admin: true, meta: {}, id: crypto.randomUUID() }), {
      headers: { "Content-Type": "application/json" },
      status: 200,
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  await devLogin("admin");

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/auth/dev-login",
    expect.objectContaining({ method: "POST" }),
  );
});
```

**Step 2: Run tests to verify failure**

Run: `npm run test -- --run src/features/auth/api.test.ts src/features/auth/AuthContext.test.tsx`

Run from: `frontend/`

Expected: FAIL because auth files are missing.

**Step 3: Implement auth client**

Create types:

```ts
export type CurrentUser = {
  id: string;
  account: string;
  is_admin: boolean;
  meta: Record<string, unknown>;
};
```

Create API functions:

```ts
export function getCurrentUser(): Promise<CurrentUser> {
  return requestJson<CurrentUser>("/api/auth/me");
}

export function devLogin(account: string): Promise<CurrentUser> {
  return requestJson<CurrentUser>("/api/auth/dev-login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ account }),
  });
}

export function logout(): Promise<CurrentUser | Record<string, never>> {
  return requestJson("/api/auth/logout", { method: "POST" });
}
```

Set `credentials: "same-origin"` in `requestJson` for explicit cookie behavior.

**Step 4: Implement auth context**

Expose:

```ts
type AuthState =
  | { status: "loading"; user: null }
  | { status: "anonymous"; user: null }
  | { status: "authenticated"; user: CurrentUser };
```

Provide `refresh()`, `loginAs(account)`, and `logout()` methods.

**Step 5: Run tests to verify pass**

Run: `npm run test -- --run src/features/auth/api.test.ts src/features/auth/AuthContext.test.tsx src/lib/apiClient.test.ts`

Run from: `frontend/`

Expected: PASS.

**Step 6: Commit**

```bash
git add frontend/src/features/auth frontend/src/lib/apiClient.ts frontend/src/lib/apiClient.test.ts
git commit -m "Add frontend auth client"
```

---

### Task 6: Add Dev User Picker And Route Authorization

**Files:**
- Create: `frontend/src/features/auth/DevUserPicker.tsx`
- Modify: `frontend/src/app/App.tsx`
- Modify: `frontend/src/app/routing/useAuthz.ts`
- Modify: `frontend/src/app/routing/ProtectedRoute.tsx`
- Modify: `frontend/src/app/App.test.tsx`
- Modify: `frontend/src/app/routing/ProtectedRoute.test.tsx`

**Step 1: Write failing UI tests**

Add tests:

```ts
it("shows dev user picker when auth bootstrap is anonymous", async () => {
  vi.mocked(getCurrentUser).mockRejectedValue(
    new ApiError(401, "Unauthorized", "Authentication required."),
  );

  render(<App />);

  expect(await screen.findByRole("button", { name: /common/i })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /admin/i })).toBeInTheDocument();
});
```

Update protected route tests to mock the auth context instead of `useAuthz` if
that is simpler after refactor.

**Step 2: Run tests to verify failure**

Run: `npm run test -- --run src/app/App.test.tsx src/app/routing/ProtectedRoute.test.tsx`

Run from: `frontend/`

Expected: FAIL until the picker and provider are wired.

**Step 3: Implement dev picker**

Use `DESIGN.md` tokens and existing Tailwind conventions. Keep the screen
compact and application-like; do not add a marketing landing page.

The picker should show two primary choices:

| Account | Label |
| --- | --- |
| `common` | Common |
| `admin` | Admin |

On click, call `loginAs(account)`. Disable buttons while submitting and show
the API error detail if login fails.

**Step 4: Wire app bootstrap**

Wrap the app in `AuthProvider`. Before rendering `WorkspaceFrame`:

- `loading`: render a minimal loading state.
- `anonymous` and `import.meta.env.DEV`: render `DevUserPicker`.
- `anonymous` and non-dev: render a plain auth-required state.
- `authenticated`: render existing routes.

**Step 5: Wire authorization**

Change `useAuthz()` to read the auth context:

```ts
export function useAuthz(): AuthzState {
  const { user } = useAuth();
  return { isAdmin: user?.is_admin === true };
}
```

Keep `ProtectedRoute` behavior simple: non-admin returns `403 Forbidden`.

**Step 6: Run tests to verify pass**

Run: `npm run test -- --run src/app/App.test.tsx src/app/routing/ProtectedRoute.test.tsx src/features/auth`

Run from: `frontend/`

Expected: PASS.

**Step 7: Commit**

```bash
git add frontend/src/features/auth/DevUserPicker.tsx frontend/src/app/App.tsx frontend/src/app/routing/useAuthz.ts frontend/src/app/routing/ProtectedRoute.tsx frontend/src/app/App.test.tsx frontend/src/app/routing/ProtectedRoute.test.tsx
git commit -m "Add dev user picker"
```

---

### Task 7: Update API Contract, Makefile, And Final Verification

**Files:**
- Modify: `api/openapi.yml`
- Modify: `tests/test_openapi_contract.py`
- Modify: `Makefile`
- Modify: `frontend/README.md`
- Modify: `docs/frontend.md`

**Step 1: Write failing contract tests**

Extend `tests/test_openapi_contract.py`:

```python
def test_auth_paths_are_documented() -> None:
    contract = load_contract()
    paths = contract["paths"]

    assert "/api/auth/me" in paths
    assert "/api/auth/dev-login" in paths
    assert "/api/auth/logout" in paths
    assert "CookieAuth" in contract["components"]["securitySchemes"]
    assert "UserPublic" in contract["components"]["schemas"]
```

**Step 2: Run tests to verify failure**

Run: `uv run pytest tests/test_openapi_contract.py -v`

Expected: FAIL until `api/openapi.yml` is updated.

**Step 3: Update OpenAPI**

Add:

- `auth` tag.
- `CookieAuth` security scheme: `type: apiKey`, `in: cookie`,
  `name: cqa_user`.
- `UserPublic` and `DevLoginRequest` schemas.
- `/api/auth/me`, `/api/auth/dev-login`, `/api/auth/logout` paths.
- 401 responses for protected API paths.
- MCP operations should document `CookieAuth`; backend route dependencies enforce
  that the authenticated user is an admin. Do not document or send a separate
  MCP credential gate.

**Step 4: Update dev scripts and docs**

Update `Makefile`:

```make
dev:
	LOG_LEVEL=$${LOG_LEVEL:-INFO} ACCESS_LOG_ENABLED=$${ACCESS_LOG_ENABLED:-true} AUTH_DEV_MODE=$${AUTH_DEV_MODE:-true} uv run fastapi dev --host $(HOST) --port $(PORT)
```

Document in frontend docs that Vite dev shows a user picker backed by
`/api/auth/dev-login`.

**Step 5: Run backend verification**

Run: `uv run pytest tests/test_openapi_contract.py tests/test_auth_api.py tests/test_auth_middleware.py tests/test_config.py tests/test_models.py tests/test_migrations.py -v`

Expected: PASS.

Run: `make test`

Expected: PASS, except database-marked tests may skip when `TEST_DATABASE_URL`
is not configured.

**Step 6: Run frontend verification**

Run from `frontend/`: `npm run test`

Expected: PASS.

Run from `frontend/`: `npm run build`

Expected: PASS.

**Step 7: Manual dev smoke test**

Run backend from repo root:

```bash
make dev
```

Run frontend from `frontend/`:

```bash
npm run dev
```

Verify:

1. Open `http://localhost:5173`.
2. Dev user picker appears.
3. Select `common`; SOP page loads; `/mcp` shows 403.
4. Logout or clear cookie, select `admin`; `/mcp` route renders.
5. Start an SOP run; run-event streaming still works.

**Step 8: Commit**

```bash
git add api/openapi.yml tests/test_openapi_contract.py Makefile frontend/README.md docs/frontend.md
git commit -m "Document auth contract and dev workflow"
```

---

### Final Review Checklist

Run:

```bash
git status --short
uv run pytest
npm run test
npm run build
```

Expected:

- Worktree is clean after commits.
- Backend tests pass.
- Frontend tests and build pass.
- No `.agents/` or `skills-lock.json` files are staged.
- `refresh_token` is never returned by API responses.
- Native `EventSource` keeps working because auth uses cookies.
