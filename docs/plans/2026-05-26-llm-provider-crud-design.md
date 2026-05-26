# LLM Provider CRUD Design

Date: 2026-05-26

## Context

The project needs CRUD APIs for configuring LLM providers. This capability will
later be populated through SSO-authenticated user identity, so v1 should make
the identity boundary explicit without coupling the rest of the backend to the
final SSO implementation.

The provider store should also support regular API keys, not only LLM provider
credentials. The first public product surface remains LLM provider CRUD.

## Goals

- Let users manage their own LLM provider credentials.
- Keep global provider credentials hidden from regular users.
- Let admins manage global LLM provider credentials.
- Prefer user-owned credentials when runtime code later resolves a provider.
- Store enough shape to support OpenAI-style and OpenAI-compatible providers.
- Keep the data model general enough for regular API keys.
- Introduce a fake FastAPI auth middleware that can later be replaced by SSO.

## Non-Goals

- Do not implement real SSO in this change.
- Do not expose global provider data to regular users.
- Do not expose CRUD APIs for regular API keys yet.
- Do not build frontend management pages in this change.
- Do not finalize KMS or secret manager integration in v1.

## Recommended Approach

Use one table as a generic credential registry. Records are separated by
`credential_type`, `scope`, and `owner_user_id`.

This keeps the current feature simple while leaving room for regular API keys
and future background sync jobs. It also keeps SSO integration local: later work
can replace how the current user is loaded without changing route-level
authorization rules.

Rejected alternatives:

- Separate user and global tables: clearer physical separation, but more
  duplicated CRUD and harder fallback resolution.
- Provider table plus access mapping table: more flexible, but unnecessary for
  the current user-owned/global-owned boundary.

## Authentication Boundary

Add a fake FastAPI authentication middleware for v1.

The middleware reads:

```text
X-User-Id: user-123
X-User-Role: user | admin
```

It attaches a current user object to `request.state.current_user`.

Dependency helpers should expose:

- `CurrentUserDep`: requires a user and returns the current user.
- `AdminUserDep`: requires the current user to have role `admin`.

Missing identity returns `401 Unauthorized`. Non-admin access to admin routes
returns `403 Forbidden`.

Future SSO work should replace the middleware identity source, not the route or
repository contracts.

## Data Model

Create `provider_credentials`.

Recommended columns:

```text
id UUID primary key
credential_type TEXT not null
scope TEXT not null
owner_user_id TEXT nullable
name TEXT not null
provider TEXT nullable
base_url TEXT nullable
api_key_ciphertext TEXT not null
api_key_hint TEXT not null
model TEXT nullable
metadata JSONB not null default '{}'
is_active BOOL not null default true
created_by TEXT nullable
updated_by TEXT nullable
created_at TIMESTAMPTZ not null
updated_at TIMESTAMPTZ not null
```

Supported values:

```text
credential_type: llm_provider | api_key
scope: user | global
```

Constraints:

- `scope = 'user'` requires `owner_user_id`.
- `scope = 'global'` requires `owner_user_id IS NULL`.
- Names are unique per user for user-scoped records.
- Names are unique for global records.

For v1, `api_key_ciphertext` may store an unencrypted placeholder value behind
an internal helper, but the field and service API should be shaped as encrypted
storage. This lets KMS or a secret manager replace the helper later.

API responses must never return `api_key` or `api_key_ciphertext`. They return
only `api_key_hint`, for example `sk-...abcd`.

## User API

User-facing routes manage only the caller's `llm_provider` records.

```text
GET    /api/llm-providers
POST   /api/llm-providers
GET    /api/llm-providers/{provider_id}
PATCH  /api/llm-providers/{provider_id}
DELETE /api/llm-providers/{provider_id}
```

Rules:

- `GET /api/llm-providers` returns only `scope = user` records owned by the
  current user.
- `POST /api/llm-providers` always creates `credential_type = llm_provider`,
  `scope = user`, and `owner_user_id = current_user.id`.
- Reading, updating, or deleting another user's provider returns `404 Not
  Found`.
- Global providers are never visible through these routes.
- `DELETE` is a soft delete that sets `is_active = false` and returns `204 No
  Content`.

Create request:

```json
{
  "name": "OpenAI personal",
  "provider": "openai",
  "base_url": "https://api.openai.com/v1",
  "api_key": "sk-...",
  "model": "gpt-4.1-mini",
  "metadata": {}
}
```

Response:

```json
{
  "id": "uuid",
  "name": "OpenAI personal",
  "provider": "openai",
  "base_url": "https://api.openai.com/v1",
  "api_key_hint": "sk-...abcd",
  "model": "gpt-4.1-mini",
  "metadata": {},
  "is_active": true,
  "created_at": "2026-05-26T00:00:00Z",
  "updated_at": "2026-05-26T00:00:00Z"
}
```

`PATCH` supports partial updates. If `api_key` is absent, the existing secret
and hint are preserved.

## Admin API

Admin routes manage only global `llm_provider` records.

```text
GET    /api/admin/llm-providers
POST   /api/admin/llm-providers
GET    /api/admin/llm-providers/{provider_id}
PATCH  /api/admin/llm-providers/{provider_id}
DELETE /api/admin/llm-providers/{provider_id}
```

Rules:

- Only admins can access these routes.
- `POST` always creates `credential_type = llm_provider`, `scope = global`, and
  `owner_user_id = NULL`.
- Admin list/read/update/delete operate only on global records.
- Deletion is soft deletion with `204 No Content`.

## Runtime Resolution

Runtime provider resolution is not part of this CRUD change, but the intended
future behavior is:

1. Look for an active user-scoped provider for the current user.
2. If none exists, let internal runtime code use an active global provider.
3. Do not expose which global provider was selected through user-facing APIs.

This matches the product rule: user configuration has priority, global
providers are system/admin resources.

## Error Handling

- `401`: missing or invalid current user identity.
- `403`: authenticated user is not allowed to access an admin route.
- `404`: provider does not exist, is inactive, or is outside the caller's
  allowed scope.
- `409`: duplicate provider name in the same ownership scope.
- `422`: request validation error.

## Implementation Shape

Expected files:

```text
app/api/auth.py
app/api/deps.py
app/api/v1/llm_providers.py
app/api/v1/admin_llm_providers.py
app/models/provider_credentials.py
app/repositories/provider_credentials.py
app/schemas/llm_providers.py
migrations/versions/<revision>_create_provider_credentials.py
api/openapi.yml
```

`app/main.py` should register the fake auth middleware and include both routers.
The repository should enforce owner/scope filters so authorization does not live
only in route functions.

## Testing

Backend tests should cover:

- Missing `X-User-Id` returns `401`.
- Regular users can create, list, read, update, and soft-delete their own
  provider.
- Regular users cannot read or mutate another user's provider.
- Regular users cannot see global providers.
- Non-admin users receive `403` for admin routes.
- Admin users can create, list, read, update, and soft-delete global providers.
- Duplicate names in the same scope return `409`.
- Responses never include `api_key` or `api_key_ciphertext`.
- `PATCH` without `api_key` preserves the previous key hint.
- OpenAPI contains user and admin LLM provider routes.

Repository tests should cover owner/scope filtering independently from the API
routes.

