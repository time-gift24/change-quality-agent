import { useEffect, useMemo, useRef, useState } from "react";

import { RunObserver } from "../../runs/components/RunObserver";
import { startSopQualityRun } from "../api";
import { useSopEnvironments, useSopRunHistory } from "../hooks";
import type { SopRunHistoryItem } from "../types";

type ChatPageProps = {
  defaultHistorySopId?: string;
  initialSopId?: string;
  registeredNodeIds?: string[];
};

const DEFAULT_HISTORY_SOP_ID = "release-checklist";

const DEFAULT_REGISTERED_NODE_IDS = [
  "load_sop",
  "check_steps",
  "summarize_result",
];

export function ChatPage({
  defaultHistorySopId = DEFAULT_HISTORY_SOP_ID,
  initialSopId = "",
  registeredNodeIds = DEFAULT_REGISTERED_NODE_IDS,
}: ChatPageProps) {
  const [sopId, setSopId] = useState(initialSopId || defaultHistorySopId);
  const [pendingSopId, setPendingSopId] = useState(initialSopId);
  const [selectedEnv, setSelectedEnv] = useState("");
  const [observedRunId, setObservedRunId] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [startMessage, setStartMessage] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const startRequestRef = useRef(0);
  const observedRunIdRef = useRef(observedRunId);
  observedRunIdRef.current = observedRunId;

  const environments = useSopEnvironments();
  const history = useSopRunHistory(sopId, selectedEnv, historyRefreshKey);

  useEffect(() => {
    if (!selectedEnv && environments.data.length > 0) {
      setSelectedEnv(environments.data[0].key);
    }
  }, [environments.data, selectedEnv]);

  const canSend = Boolean(pendingSopId.trim()) && Boolean(selectedEnv);

  async function handleSend() {
    const nextSopId = pendingSopId.trim();
    if (!nextSopId || !selectedEnv) {
      return;
    }

    if (nextSopId !== sopId) {
      setSopId(nextSopId);
    }

    const requestId = startRequestRef.current + 1;
    const requestSopId = nextSopId;
    const requestEnv = selectedEnv;
    const observedAtStart = observedRunIdRef.current;

    startRequestRef.current = requestId;
    setStarting(true);
    setStartError(null);
    setStartMessage(null);

    try {
      const result = await startSopQualityRun(requestSopId, requestEnv);

      if (
        startRequestRef.current !== requestId ||
        observedRunIdRef.current !== observedAtStart
      ) {
        return;
      }

      setObservedRunId(result.runId);
      setHistoryRefreshKey((value) => value + 1);

      if (result.kind === "active") {
        setStartMessage(`已存在进行中的运行，已加入对话 ${result.runId}。`);
      }
    } catch (error) {
      if (startRequestRef.current !== requestId) {
        return;
      }
      setStartError(
        error instanceof Error ? error.message : "无法发起运行，请稍后再试。",
      );
    } finally {
      if (startRequestRef.current === requestId) {
        setStarting(false);
      }
    }
  }

  function handleEnvironmentChange(nextEnv: string) {
    startRequestRef.current += 1;
    setSelectedEnv(nextEnv);
    setStartError(null);
    setStartMessage(null);
    setStarting(false);
  }

  function handleNewConversation() {
    startRequestRef.current += 1;
    setObservedRunId(null);
    setStartError(null);
    setStartMessage(null);
    setStarting(false);
    setSopId(initialSopId || defaultHistorySopId);
    setPendingSopId(initialSopId);
  }

  function handleSelectHistory(runId: string) {
    setObservedRunId(runId);
    setStartError(null);
    setStartMessage(null);
  }

  return (
    <div className="flex min-h-screen bg-canvas text-ink bg-aurora">
      <Sidebar
        open={sidebarOpen}
        onToggle={() => setSidebarOpen((value) => !value)}
        history={history.data}
        loading={history.loading}
        error={history.error}
        observedRunId={observedRunId}
        onSelect={handleSelectHistory}
        onNewConversation={handleNewConversation}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <main className="flex flex-1 flex-col overflow-hidden">
          {observedRunId ? (
            <RunCanvas
              runId={observedRunId}
              registeredNodeIds={registeredNodeIds}
              startError={startError}
              startMessage={startMessage}
            />
          ) : (
            <EmptyState
              envs={environments.data}
              envsLoading={environments.loading}
              envsError={environments.error}
              selectedEnv={selectedEnv}
              onEnvChange={handleEnvironmentChange}
              sopId={pendingSopId}
              onSopIdChange={setPendingSopId}
              onConfirm={handleSend}
              canSend={canSend}
              starting={starting}
              startError={startError}
              startMessage={startMessage}
            />
          )}
        </main>
      </div>
    </div>
  );
}

function Sidebar({
  open,
  onToggle,
  history,
  loading,
  error,
  observedRunId,
  onSelect,
  onNewConversation,
}: {
  open: boolean;
  onToggle: () => void;
  history: SopRunHistoryItem[];
  loading: boolean;
  error: Error | null;
  observedRunId: string | null;
  onSelect: (runId: string) => void;
  onNewConversation: () => void;
}) {
  const [recentOpen, setRecentOpen] = useState(true);

  return (
    <aside
      aria-label="历史对话"
      className={`flex shrink-0 flex-col border-r border-hairline bg-canvas/60 backdrop-blur-sm transition-[width] duration-200 ${
        open ? "w-64" : "w-14"
      }`}
    >
      <div className="flex h-14 shrink-0 items-center gap-2 px-3">
        <button
          aria-label={open ? "收起侧边栏" : "展开侧边栏"}
          className="flex h-9 w-9 items-center justify-center rounded-full text-mute transition-colors hover:bg-canvas-soft hover:text-ink"
          onClick={onToggle}
          type="button"
        >
          <SidebarIcon />
        </button>
        {open ? (
          <span className="text-base font-semibold tracking-tight text-ink">
            质量检查
          </span>
        ) : null}
      </div>

      {open ? (
        <>
          <div className="px-3 pt-2">
            <button
              aria-label="发起新SOP质检"
              className="flex h-8 w-full items-center gap-2 rounded-xl px-2 text-xs font-medium text-body transition-colors hover:bg-canvas-soft hover:text-ink"
              onClick={onNewConversation}
              type="button"
            >
              <PencilIcon />
              <span>发起新SOP质检</span>
            </button>
          </div>

          <div className="mt-4 px-3">
            <button
              aria-expanded={recentOpen}
              aria-label="切换最近质检SOP"
              className="flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-mute transition-colors hover:text-body"
              onClick={() => setRecentOpen((value) => !value)}
              type="button"
            >
              <ChevronIcon open={recentOpen} />
              <span>最近质检SOP</span>
            </button>
          </div>

          {recentOpen ? (
            <div className="mt-1 flex-1 overflow-y-auto px-2 pb-4">
              {error ? (
                <p className="px-2 py-1 text-xs text-error-deep" role="alert">
                  {error.message}
                </p>
              ) : null}
              {loading ? (
                <p className="px-2 py-1 text-xs text-mute">加载中...</p>
              ) : null}
              {!loading && history.length === 0 && !error ? (
                <p className="px-2 py-1 text-xs text-mute">暂无历史。</p>
              ) : null}
              <ul className="space-y-0.5">
                {history.map((run) => {
                  const active = observedRunId === run.run_id;
                  return (
                    <li key={run.run_id}>
                      <button
                        aria-pressed={active}
                        className={`group flex w-full items-center gap-2 truncate rounded-full px-3 py-2 text-left text-xs transition-colors ${
                          active
                            ? "border border-primary/40 bg-canvas text-ink shadow-sm"
                            : "border border-transparent text-body hover:bg-canvas-soft"
                        }`}
                        onClick={() => onSelect(run.run_id)}
                        title={run.subject_id ?? run.run_id}
                        type="button"
                      >
                        <span className="block flex-1 truncate">
                          {historyTitle(run)}
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
        </>
      ) : null}
    </aside>
  );
}

function EmptyState({
  envs,
  envsLoading,
  envsError,
  selectedEnv,
  onEnvChange,
  sopId,
  onSopIdChange,
  onConfirm,
  canSend,
  starting,
  startError,
  startMessage,
}: {
  envs: { key: string; name_en: string; name_zh: string }[];
  envsLoading: boolean;
  envsError: Error | null;
  selectedEnv: string;
  onEnvChange: (key: string) => void;
  sopId: string;
  onSopIdChange: (value: string) => void;
  onConfirm: () => void;
  canSend: boolean;
  starting: boolean;
  startError: string | null;
  startMessage: string | null;
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4">
      <div className="w-full max-w-3xl space-y-6 text-center">
        <form
          aria-label="SOP 运行表单"
          className="flex flex-col items-center gap-3 text-left sm:flex-row sm:items-center sm:justify-center"
          onSubmit={(event) => {
            event.preventDefault();
            if (!starting && canSend) {
              onConfirm();
            }
          }}
        >
          <div className="relative w-full sm:w-52">
            <select
              aria-label="环境"
              className="h-10 w-full appearance-none rounded-xl border border-hairline bg-canvas/95 py-0 pl-3 pr-10 text-sm font-medium text-ink shadow-sm outline-none transition-colors hover:border-hairline-strong hover:bg-canvas focus:border-primary focus:ring-2 focus:ring-primary/25 disabled:cursor-not-allowed disabled:bg-canvas-soft disabled:text-mute"
              disabled={envsLoading || envs.length === 0}
              id="env-select"
              onChange={(event) => onEnvChange(event.target.value)}
              value={selectedEnv}
            >
              {envs.length === 0 ? (
                <option value="">
                  {envsLoading ? "加载中..." : "无可用环境"}
                </option>
              ) : null}
              {envs.map((env) => (
                <option key={env.key} value={env.key}>
                  {env.name_zh || env.name_en}
                </option>
              ))}
            </select>
            <span
              aria-hidden="true"
              className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-mute"
              data-testid="environment-select-chevron"
            >
              <SelectChevronIcon />
            </span>
          </div>

          <div className="sm:w-96">
            <input
              aria-label="SOP ID"
              className="h-10 w-full rounded-xl border border-hairline bg-canvas px-3 text-sm text-ink outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/25"
              id="sop-id-input"
              onChange={(event) => onSopIdChange(event.target.value)}
              placeholder="输入 SOP ID"
              value={sopId}
            />
          </div>

          <button
            aria-label="确认并发起运行"
            className="h-10 shrink-0 rounded-xl bg-primary px-5 text-sm font-medium text-on-primary shadow-sm transition-colors hover:bg-primary-deep disabled:cursor-not-allowed disabled:bg-mute"
            disabled={!canSend || starting}
            type="submit"
          >
            {starting ? "正在发起..." : "开始质检"}
          </button>
        </form>

        {envsError ? (
          <p
            className="mx-auto max-w-md rounded-xl border border-error-soft bg-canvas px-4 py-2 text-sm text-error-deep"
            role="alert"
          >
            {envsError.message}
          </p>
        ) : null}
        {startError ? (
          <p
            className="mx-auto max-w-md rounded-xl border border-error-soft bg-canvas px-4 py-2 text-sm text-error-deep"
            role="alert"
          >
            {startError}
          </p>
        ) : null}
        {startMessage ? (
          <p
            className="mx-auto max-w-md rounded-xl border border-hairline bg-canvas px-4 py-2 text-sm text-primary-deep"
            role="status"
          >
            {startMessage}
          </p>
        ) : null}
      </div>
    </div>
  );
}

function RunCanvas({
  runId,
  registeredNodeIds,
  startError,
  startMessage,
}: {
  runId: string;
  registeredNodeIds: string[];
  startError: string | null;
  startMessage: string | null;
}) {
  return (
    <div className="flex flex-1 flex-col overflow-y-auto px-4 py-6">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
        {startError ? (
          <p
            className="rounded-xl border border-error-soft bg-canvas px-4 py-2 text-sm text-error-deep"
            role="alert"
          >
            {startError}
          </p>
        ) : null}
        {startMessage ? (
          <p
            className="rounded-xl border border-hairline bg-canvas px-4 py-2 text-sm text-primary-deep"
            role="status"
          >
            {startMessage}
          </p>
        ) : null}

        <RunObserver runId={runId} registeredNodeIds={registeredNodeIds} />
      </div>
    </div>
  );
}

function SidebarIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <rect x="3" y="4" width="18" height="16" rx="3" />
      <path d="M9 4v16" />
    </svg>
  );
}

function PencilIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <path d="M16 3l5 5-12 12H4v-5z" />
      <path d="M14 5l5 5" />
    </svg>
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

function SelectChevronIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

function historyTitle(run: SopRunHistoryItem): string {
  return run.subject_id || run.run_id;
}

function statusLabel(status: string | null | undefined): string {
  switch (status) {
    case "running":
      return "进行中";
    case "success":
      return "成功";
    case "error":
      return "失败";
    case "timeout":
      return "超时";
    case "interrupted":
      return "已中断";
    case "pending":
      return "等待中";
    default:
      return status ?? "";
  }
}
