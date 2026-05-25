# Frontend

This directory is reserved for the Change Quality Agent browser app.

Fixed stack:

- Vite
- React 19
- TypeScript
- Tailwind CSS v4 via `@tailwindcss/vite`
- Streamdown for streamed markdown

The implementation plan lives at
`docs/plans/2026-05-25-runs-frontend-implementation.md`.

Before implementing UI, read `../DESIGN.md` and follow it strictly. It is the
mandatory UI contract for this frontend.

Implementation notes:

- The app shell lives in `src/app/App.tsx`; route composition lives in
  `src/app/routes.tsx`.
- Tailwind scans frontend-local Streamdown classes via
  `@source "../../node_modules/streamdown/dist/*.js"` in
  `src/styles/globals.css`.
- Streamed markdown output must be rendered with `streamdown`. Run message
  events flow through `RunEventStream` and `StreamMarkdown`.
- Generic run UI must stay SOP-agnostic and must not expose SOP `env_key`.
- The SOP quality page is a thin wrapper over the generic `RunObserver`.
