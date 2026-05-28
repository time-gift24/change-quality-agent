# Auth

This document describes the current user authentication and authorization flow,
plus the intended path for connecting the internal OAuth2 provider.

## Current Model

The system only distinguishes normal users and admin users.

| Role | Backend flag | SOP access | MCP access |
| --- | --- | --- | --- |
| Normal | `is_admin=false` | Allowed | Rejected |
| Admin | `is_admin=true` | Allowed | Allowed |

User records are stored in `users` with:

| Field | Purpose |
| --- | --- |
| `account` | Stable internal user account identifier |
| `refresh_token` | Placeholder for future OAuth2 refresh token storage |
| `is_admin` | Backend authority for admin-only features |
| `meta` | Provider or internal profile metadata |

## Local Development Login

`make dev` starts the backend with `AUTH_DEV_MODE=true`. On startup, the backend
seeds two development users:

| Account | Admin |
| --- | --- |
| `common` | No |
| `admin` | Yes |

The dev login endpoint is `POST /api/auth/dev-login`. It accepts an account,
loads the seeded user, and writes the configured HTTP-only cookie:

```text
cqa_user=<account>
```

This cookie is a local development convenience. It is not the production OAuth2
session mechanism.

## Backend Request Flow

Authentication is enforced by the FastAPI HTTP middleware in `app/main.py`.

1. Requests outside `/api/` pass through without API auth.
2. Bypass paths pass through without an existing user:
   - `/health`
   - `/docs`
   - `/redoc`
   - `/openapi.json`
   - `/api/auth/dev-login`
   - `/api/auth/logout`
3. Protected API requests call `resolve_current_user(request)`.
4. If no user is resolved, the backend returns `401 Authentication required.`
   and clears a stale auth cookie when present.
5. If a user is resolved, middleware stores it on:

```python
request.state.current_user = current_user
```

Current development resolution lives in `app/core/security.py`:

1. Read `settings.auth_session_cookie_name` from request cookies.
2. Treat the cookie value as `account` while `auth_dev_mode=true`.
3. Load the user with `UserRepository.get_by_account(account)`.
4. Return a lightweight `CurrentUser` containing `id`, `account`, `is_admin`,
   and `meta`.

## Admin Authorization

Authentication answers "who is this user?". Authorization answers "can this user
access this feature?".

Admin-only backend APIs use `require_admin_user` from `app/api/deps.py`. The
dependency reads `request.state.current_user` and rejects missing or normal users
with `403 Admin access required.`

The MCP router applies this dependency at the router level:

```python
router = APIRouter(
    prefix="/api/mcp",
    tags=["mcp"],
    dependencies=[Depends(require_admin_user)],
)
```

This means every `/api/mcp/*` endpoint requires an authenticated admin user.
There is no separate MCP token or custom MCP auth header.

## Frontend Flow

The frontend calls `GET /api/auth/me` during app bootstrap.

| Backend result | Frontend behavior |
| --- | --- |
| `200` with user | Enter workspace |
| `401` in Vite dev | Show the dev user picker |
| `401` outside dev | Show authentication required state |

The frontend authorization state is derived from the backend user:

```ts
isAdmin = user?.is_admin === true
```

`workspaceRoutes` marks MCP as `requiresAdmin=true`. The sidebar hides MCP for
normal users, and direct navigation to `/mcp` renders a 403 page. This is only a
user experience guard; the backend `require_admin_user` dependency is the real
security boundary.

API calls use same-origin credentials so browser cookies are included. Native
`EventSource` run streams also carry cookies automatically.

## OAuth2 Integration Plan

The preferred production shape is a backend-for-frontend OAuth2 flow. The browser
does not receive or store provider access tokens. The backend completes OAuth2,
then writes the application session cookie.

```text
Browser
  -> GET /api/auth/login
Backend
  -> redirect to internal OAuth2 authorize URL
Provider
  -> GET /api/auth/callback?code=...&state=...
Backend
  -> exchange code for tokens
  -> load user profile or decode id_token
  -> upsert users(account, refresh_token, is_admin, meta)
  -> set secure HTTP-only app session cookie
  -> redirect to /sop
```

### Backend Changes

Add settings in `app/core/config.py`:

| Setting | Purpose |
| --- | --- |
| `oauth2_client_id` | Internal OAuth2 client ID |
| `oauth2_client_secret` | Internal OAuth2 client secret |
| `oauth2_authorize_url` | Provider authorization endpoint |
| `oauth2_token_url` | Provider token endpoint |
| `oauth2_userinfo_url` | Provider userinfo endpoint, if used |
| `oauth2_redirect_uri` | Callback URL registered with provider |
| `oauth2_scopes` | Requested scopes |
| `oauth2_admin_groups` | Provider groups mapped to admin access |
| `oauth2_admin_accounts` | Optional account allowlist for admin access |

Add endpoints in `app/api/v1/auth.py`:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/auth/login` | Generate `state`, store it securely, redirect to provider |
| `GET /api/auth/callback` | Validate `state`, exchange code, upsert user, set session cookie |
| `GET /api/auth/me` | Keep returning the current `UserPublic` |
| `POST /api/auth/logout` | Clear the app session cookie |

Refactor `app/core/security.py`:

```python
async def resolve_current_user(request: Request) -> CurrentUser | None:
    if settings.auth_dev_mode:
        user = await resolve_dev_user(request)
        if user is not None:
            return user

    return await resolve_oauth_session_user(request)
```

`resolve_oauth_session_user` should verify the production app session cookie,
load the corresponding user, and return the same `CurrentUser` shape used today.
Downstream code should not care whether the user came from dev login or OAuth2.

### User Mapping

The OAuth2 callback should map provider identity into the existing user model:

| User field | Source |
| --- | --- |
| `account` | Stable provider account, username, or employee ID |
| `refresh_token` | Provider refresh token, encrypted before storage |
| `is_admin` | Derived from provider groups, roles, or account allowlist |
| `meta` | Non-secret profile fields such as display name, email, groups, department |

The frontend must never decide `is_admin`. It only renders the backend result.

### Session And Security Requirements

- Use `HttpOnly`, `Secure`, and `SameSite=Lax` or stricter cookies in production.
- Validate OAuth2 `state` to prevent CSRF during login.
- Use Authorization Code flow. Add PKCE if the internal provider supports or
  requires it.
- Do not expose access tokens or refresh tokens to the browser.
- Encrypt refresh tokens before storing them in `users.refresh_token`.
- Keep token refresh and profile sync in backend code.
- Preserve the existing `request.state.current_user` contract so service and
  agent layers remain auth-provider agnostic.

## What Should Not Change

- SOP and MCP services should not know OAuth2 details.
- Agent code should not read cookies, tokens, or provider claims.
- MCP authorization should continue to depend only on
  `request.state.current_user.is_admin`.
- Frontend route guards should remain a convenience layer, not the security
  boundary.
