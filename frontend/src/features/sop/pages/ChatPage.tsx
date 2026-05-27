import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useWorkspaceLayout } from "../../../app/WorkspaceLayoutContext";
import { RunObserver } from "../../runs/components/RunObserver";
import { startSopQualityRun } from "../api";
import { useSopEnvironments } from "../hooks";

type ChatPageProps = {
  initialSopId?: string;
  registeredNodeIds?: string[];
};

const DEFAULT_REGISTERED_NODE_IDS = [
  "load_sop",
  "check_steps",
  "summarize_result",
];

export function ChatPage({
  initialSopId = "",
  registeredNodeIds = DEFAULT_REGISTERED_NODE_IDS,
}: ChatPageProps) {
  const [sopId, setSopId] = useState(initialSopId);
  const [pendingSopId, setPendingSopId] = useState(initialSopId);
  const [selectedEnv, setSelectedEnv] = useState("");
  const [observedRunId, setObservedRunId] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [startMessage, setStartMessage] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const startRequestRef = useRef(0);
  const observedRunIdRef = useRef(observedRunId);
  observedRunIdRef.current = observedRunId;

  const environments = useSopEnvironments();

  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { refreshRecentSopRuns, setNewConversationHandler, setSidebarContent } = useWorkspaceLayout();
  const routeRunId = searchParams.get("runId");

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
      refreshRecentSopRuns();
      navigate(`/sop?runId=${result.runId}`, { replace: true });

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

  const handleNewConversation = useCallback(() => {
    startRequestRef.current += 1;
    setObservedRunId(null);
    setStartError(null);
    setStartMessage(null);
    setStarting(false);
    setSopId(initialSopId);
    setPendingSopId(initialSopId);
    navigate("/sop", { replace: true });
  }, [initialSopId, navigate]);

  useEffect(() => {
    setNewConversationHandler(handleNewConversation);
    setSidebarContent(null);

    return () => {
      setNewConversationHandler(null);
      setSidebarContent(null);
    };
  }, [handleNewConversation, setNewConversationHandler, setSidebarContent]);

  useEffect(() => {
    if (!routeRunId) return;
    setObservedRunId(routeRunId);
    setStartError(null);
    setStartMessage(null);
  }, [routeRunId]);

  return (
    <main
      aria-label="SOP 质检主内容"
      className="flex min-h-0 flex-1 flex-col overflow-hidden"
    >
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
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center overflow-y-auto px-4">
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
            className="tech-primary-button h-10 shrink-0 rounded-full px-5 text-sm font-semibold text-on-primary transition-transform hover:-translate-y-px disabled:cursor-not-allowed disabled:translate-y-0"
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
    <div className="min-h-0 flex-1 overflow-y-auto px-4 py-6">
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
