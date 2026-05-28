# User Module And Dev Auth Design

## Goal

Introduce a simple user module that can later be connected to the internal
OAuth2 provider. The first version records `account`, `refresh_token`,
`is_admin`, and `meta`, enforces authenticated API access, and keeps local
development usable with two built-in users: `common` and `admin`.

## Selected Approach

Use a cookie-backed dev session.

The frontend dev user picker calls a backend dev login endpoint. The backend
sets an HTTP-only cookie containing the selected account. Regular `fetch`
requests and native `EventSource` run-event streams then carry the same
identity automatically. This avoids custom auth headers, which do not work with
native `EventSource`.

## Backend Design

Add a `users` table:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `account` | text | Unique, required |
| `refresh_token` | text | Required for persisted OAuth2 refresh token |
| `is_admin` | boolean | Required, defaults to `false` |
| `meta` | JSONB | Required, defaults to `{}` |
| `created_at` | timestamptz | Server default `now()` |
| `updated_at` | timestamptz | Server default `now()`, updated on change |

Add `UserRepository` with minimal methods:

| Method | Purpose |
| --- | --- |
| `get_by_account(account)` | Resolve authenticated requests |
| `upsert_user(...)` | Seed dev users and later sync OAuth2 user data |

Add auth settings in `app/core/config.py`:

| Setting | Default | Purpose |
| --- | --- | --- |
| `auth_enabled` | `true` | Enable API authentication middleware |
| `auth_dev_mode` | `false` | Allow dev login endpoint and seeded users |
| `auth_session_cookie_name` | `cqa_user` | Cookie used by dev session |

`make dev` should start FastAPI with `AUTH_DEV_MODE=true`. During app startup,
the backend ensures the `common` and `admin` users exist:

| Account | `is_admin` | `refresh_token` | `meta` |
| --- | --- | --- | --- |
| `common` | `false` | dev placeholder | `{"source": "dev"}` |
| `admin` | `true` | dev placeholder | `{"source": "dev"}` |

Add auth endpoints under `/api/auth`:

| Endpoint | Behavior |
| --- | --- |
| `GET /api/auth/me` | Return current user or 401 |
| `POST /api/auth/dev-login` | Dev-only; accept `account`, set cookie |
| `POST /api/auth/logout` | Clear cookie |

## Middleware Design

Add a FastAPI HTTP middleware in `app/main.py` that protects `/api/*` by
default. It should bypass:

| Path | Reason |
| --- | --- |
| `/health` | Service health check |
| `/docs`, `/redoc`, `/openapi.json` | Local API docs |
| `/api/auth/dev-login` | Needed before a session exists |
| `/api/auth/logout` | Safe to call without a valid session |

For protected API requests, the middleware resolves the current user from the
dev session cookie while `auth_dev_mode=true`. If the user is missing or not
found, it returns 401. If found, it stores the user on `request.state.current_user`
for route dependencies and services.

MCP server configuration operations are restricted to authenticated admin users.
The previous separate MCP credential gate is intentionally removed, so frontend
and backend authorization both depend on the same user session and `is_admin`
flag.

## Frontend Design

In Vite dev mode, the app starts with an auth bootstrap:

1. Call `GET /api/auth/me`.
2. If authenticated, render the existing app.
3. If 401, render a compact user picker for `common` and `admin`.
4. On selection, call `POST /api/auth/dev-login`, then re-run auth bootstrap.

The selected user is stored only in the backend cookie. Frontend state keeps the
returned user object for rendering and authorization.

`useAuthz()` should read the current user and return `isAdmin` from
`currentUser.is_admin`. This keeps MCP route protection aligned with the backend
user model:

| User | SOP | MCP pages |
| --- | --- | --- |
| `common` | Allowed | Blocked by frontend route guard |
| `admin` | Allowed | Allowed |

SOP run event streaming continues to use native `EventSource`; no custom header
support is required because the browser sends the auth cookie.

## Error Handling

| Case | Response |
| --- | --- |
| Missing session cookie | 401 `Authentication required.` |
| Unknown account in cookie | 401 and clear stale cookie if practical |
| Dev login while `auth_dev_mode=false` | 404 or 403 |
| Dev login with unsupported account | 404 |
| Authenticated non-admin opens MCP page | Frontend 403 route guard |
| Authenticated non-admin calls MCP API | Existing MCP admin dependency still rejects without token |

## Testing

Backend tests should cover:

| Area | Test |
| --- | --- |
| Migration/model | `users` table shape, defaults, unique account |
| Repository | create/update via upsert, get by account |
| Middleware | `/api/sop/environments` returns 401 without cookie |
| Middleware | authenticated cookie allows protected API |
| Dev auth | `common` and `admin` are seeded in dev mode |
| Dev auth | `/api/auth/me`, `/api/auth/dev-login`, `/api/auth/logout` behavior |
| MCP interaction | non-admin requests are rejected by MCP API dependencies |

Frontend tests should cover:

| Area | Test |
| --- | --- |
| Auth bootstrap | 401 shows dev user picker |
| Auth bootstrap | successful login renders app |
| Authorization | `common` cannot access MCP route |
| Authorization | `admin` can access MCP route |
| API client/SSE | no custom auth header dependency is introduced |

## Deferred

| Item | Reason |
| --- | --- |
| Full OAuth2 callback/token exchange | Internal OAuth2 integration comes later |
| Password login | Not needed for internal OAuth2 |
| JWT issuance | Cookie-backed dev session is enough for local development |
| Refresh-token encryption | Needs a project-wide secret management decision |
| User management UI | Current need is identity persistence and auth context |
