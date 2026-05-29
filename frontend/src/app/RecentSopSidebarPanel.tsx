import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import {
  useRecentSopQualityChecks,
  useSopEnvironments,
} from "../features/sop/hooks";
import type { SopQualityCheckHistoryItem } from "../features/sop/types";

export function RecentSopSidebarPanel({ refreshKey = 0 }: { refreshKey?: number }) {
  const [recentOpen, setRecentOpen] = useState(true);
  const [selectedEnv, setSelectedEnv] = useState("");
  const environments = useSopEnvironments();
  const history = useRecentSopQualityChecks(selectedEnv, refreshKey);
  const navigate = useNavigate();
  const location = useLocation();
  const activeCheckId = new URLSearchParams(location.search).get("checkId");
  const historyScrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!selectedEnv && environments.data.length > 0) {
      setSelectedEnv(environments.data[0].key);
    }
  }, [environments.data, selectedEnv]);

  useEffect(() => {
    const scrollArea = historyScrollRef.current;
    if (!recentOpen || history.loading || history.data.length === 0 || !scrollArea) {
      return;
    }

    scrollArea.scrollTop = scrollArea.scrollHeight;
  }, [history.data.length, history.loading, recentOpen]);

  return (
    <div className="flex h-full flex-col">
      <div className="mt-2 px-3">
        <button
          aria-expanded={recentOpen}
          aria-label="切换最近质检SOP"
          className="flex w-full items-center justify-between rounded-md px-2 py-1 text-xs font-medium text-mute transition-colors hover:text-body"
          onClick={() => setRecentOpen((value) => !value)}
          type="button"
        >
          <span>最近质检SOP</span>
          <ChevronIcon open={recentOpen} />
        </button>
      </div>

      {recentOpen ? (
        <div
          className="mt-1 min-h-0 flex-1 overflow-y-auto px-2 pb-4"
          data-testid="recent-sop-scroll-area"
          ref={historyScrollRef}
        >
          {environments.error ? (
            <p className="px-2 py-1 text-xs text-error-deep" role="alert">
              {environments.error.message}
            </p>
          ) : null}
          {history.error ? (
            <p className="px-2 py-1 text-xs text-error-deep" role="alert">
              {history.error.message}
            </p>
          ) : null}
          {environments.loading || history.loading ? (
            <p className="px-2 py-1 text-xs text-mute">加载中...</p>
          ) : null}
          {!environments.loading && !history.loading && history.data.length === 0 && !environments.error && !history.error ? (
            <p className="px-2 py-1 text-xs text-mute">暂无历史。</p>
          ) : null}
          <ul className="space-y-0.5">
            {history.data.map((check) => {
              const active = activeCheckId === check.check_id;
              return (
                <li key={check.check_id}>
                  <button
                    aria-pressed={active}
                    className={`group flex w-full items-center gap-2 truncate rounded-full px-3 py-2 text-left text-xs transition-colors ${
                      active
                        ? "border border-primary/40 bg-canvas text-ink shadow-sm"
                        : "border border-transparent text-body hover:bg-canvas-soft"
                    }`}
                    onClick={() => navigate(`/sop?checkId=${check.check_id}`)}
                    title={check.sop_id ?? check.check_id}
                    type="button"
                  >
                    <span className="block flex-1 truncate">
                      {historyTitle(check)}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ) : (
        <div className="flex-1" />
      )}
    </div>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      aria-hidden="true"
      className={`h-3 w-3 transition-transform ${open ? "rotate-90" : ""}`}
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
    >
      <path d="M9 6l6 6-6 6" />
    </svg>
  );
}

function historyTitle(check: SopQualityCheckHistoryItem): string {
  return check.sop_id || check.check_id;
}
