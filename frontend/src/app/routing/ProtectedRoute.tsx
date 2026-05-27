import { Link, Outlet } from "react-router-dom";

import { useAuthz } from "./useAuthz";

export function ProtectedRoute() {
  const { isAdmin } = useAuthz();

  if (!isAdmin) {
    return (
      <main
        aria-labelledby="forbidden-title"
        className="flex min-h-0 flex-1 items-center justify-center overflow-auto px-4 py-6"
      >
        <section className="min-w-0 w-full max-w-sm rounded-2xl border border-hairline-soft bg-canvas/95 p-4 text-center shadow-sm shadow-primary/5">
          <p className="text-2xs font-semibold uppercase tracking-normal text-primary-deep">
            Access denied
          </p>
          <h1
            className="mt-1 text-base font-semibold tracking-tight text-ink"
            id="forbidden-title"
          >
            403 Forbidden
          </h1>
          <p className="mt-2 text-xs leading-relaxed text-body">
            Admin access is required to manage MCP servers.
          </p>
          <Link
            className="mt-4 inline-flex h-9 items-center justify-center rounded-full bg-primary px-4 text-xs font-semibold text-on-primary transition-colors hover:bg-primary-deep"
            to="/sop"
          >
            Back to SOP
          </Link>
        </section>
      </main>
    );
  }

  return <Outlet />;
}
