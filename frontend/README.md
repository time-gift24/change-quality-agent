# Frontend

This directory is reserved for the Change Quality Agent browser app.

Fixed stack:

- Vite
- React 19
- React Router
- TypeScript
- Tailwind CSS v4 via `@tailwindcss/vite`
- Streamdown for streamed markdown

The frontend architecture summary lives at `../docs/frontend.md`.

Before implementing UI, read `../DESIGN.md` and follow it strictly. It is the
mandatory UI contract for this frontend.

Implementation notes:

- The app shell lives in `src/app/App.tsx`, mounts `BrowserRouter`, and
  renders pages through `src/app/AppShell.tsx`.
- Routes:
  - `/` redirects to `/sop`.
  - `/sop` renders the SOP quality page.
  - `/mcp` renders the route-guarded MCP management page for server CRUD,
    lifecycle actions, and tool snapshots. Access requires an authenticated
    admin user.
  - `/llm-providers` renders the route-guarded LLM provider CRUD pages for
    ordinary LangChain `init_chat_model` providers. Access requires an
    authenticated admin user.
- In Vite dev mode, an unauthenticated browser session shows a `common` /
  `admin` user picker backed by `POST /api/auth/dev-login`. Choosing a user
  creates the `cqa_user` dev session cookie and reloads the auth bootstrap.
- Tailwind scans frontend-local Streamdown classes via
  `@source "../../node_modules/streamdown/dist/*.js"` in
  `src/styles/globals.css`.
- Streamed markdown output must be rendered with `streamdown`.
- SOP quality check state lives in `src/features/sop-quality-checks`, observes
  checks by `checkId`, and connects to
  `/api/sop-quality-checks/{check_id}/stream?after=<sequence>`.
- The recent SOP sidebar reads `/api/sop-quality-checks?env=<env_key>&limit=50`
  and navigates to `/sop?checkId=<check_id>`.
- MCP management is isolated in `src/features/mcp` and calls only the
  `/api/mcp/servers` API family defined in `../api/openapi.yml`.
- LLM provider management is isolated in `src/features/llmProviders` and calls
  only the `/api/v1/llm-providers` API family defined in `../api/openapi.yml`.
