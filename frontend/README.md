# Frontend

This directory is reserved for the Change Quality Agent browser app.

Fixed stack:

- Vite
- React 19
- TypeScript
- Tailwind CSS v4 via `@tailwindcss/vite`
- Streamdown for streamed markdown

The frontend architecture summary lives at `../docs/frontend.md`.

Before implementing UI, read `../DESIGN.md` and follow it strictly. It is the
mandatory UI contract for this frontend.

Implementation notes:

- The app shell lives in `src/app/App.tsx` and mounts the SOP quality page.
- Tailwind scans frontend-local Streamdown classes via
  `@source "../../node_modules/streamdown/dist/*.js"` in
  `src/styles/globals.css`.
- Streamed markdown output must be rendered with `streamdown`. Run message
  events flow through `RunEventStream` and `StreamMarkdown`.
- Generic run UI must stay SOP-agnostic and must not expose SOP `env_key`.
- The SOP quality page is a thin wrapper over the generic `RunObserver`.
