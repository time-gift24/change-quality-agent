import { AppRoutes, appRoutes } from "./routes";

export function App() {
  const activeRoute = appRoutes[0];

  return (
    <div className="min-h-screen bg-white text-[#212121]">
      <header
        aria-label="Application header"
        className="border-b border-[#d9d9dd] bg-white"
      >
        <div className="mx-auto flex h-12 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <h1 className="truncate text-sm font-medium text-[#17171c]">
              Change Quality Agent
            </h1>
            <span className="h-4 w-px bg-[#d9d9dd]" aria-hidden="true" />
            <span className="truncate text-xs text-[#75758a]">
              {activeRoute.label}
            </span>
          </div>
          <nav aria-label="Primary" className="text-xs text-[#616161]">
            <a
              aria-current="page"
              className="rounded px-2 py-1 text-[#17171c] outline-none focus-visible:ring-2 focus-visible:ring-[#4c6ee6]"
              href={activeRoute.path}
            >
              SOP
            </a>
          </nav>
        </div>
      </header>

      <AppRoutes />
    </div>
  );
}
