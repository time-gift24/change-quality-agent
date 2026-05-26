import { useRun } from "../hooks";
import { getOrderedNodeIds, type RunViewState } from "../reducer";
import type { RunSummary } from "../types";
import { StreamMarkdown } from "./StreamMarkdown";

type RunObserverProps = {
  runId: string;
  registeredNodeIds?: string[];
};

type RunObserverViewProps = {
  summary: RunSummary;
  state: RunViewState;
  registeredNodeIds?: string[];
};

const DEFAULT_REGISTERED_NODE_IDS = [
  "load_sop",
  "check_steps",
  "summarize_result",
];

export function RunObserver({
  runId,
  registeredNodeIds = DEFAULT_REGISTERED_NODE_IDS,
}: RunObserverProps) {
  const { summary, summaryError, summaryLoading, events } = useRun(runId);

  if (summaryError) {
    return (
      <section
        aria-label="Run observer"
        className="rounded-2xl border border-hairline bg-canvas px-4 py-3 text-sm text-error-deep"
        role="alert"
      >
        {summaryError.message}
      </section>
    );
  }

  if (!summary) {
    return (
      <section
        aria-label="Run observer"
        className="rounded-2xl border border-hairline bg-canvas px-4 py-3 text-sm text-body"
      >
        {summaryLoading ? "正在加载运行..." : "运行不存在或已过期。"}
      </section>
    );
  }

  return (
    <RunObserverView
      summary={summary}
      state={events}
      registeredNodeIds={registeredNodeIds}
    />
  );
}

export function RunObserverView({
  summary,
  state,
  registeredNodeIds = DEFAULT_REGISTERED_NODE_IDS,
}: RunObserverViewProps) {
  const orderedNodeIds = getOrderedNodeIds(state, registeredNodeIds);
  const runError = collectRunError(state, summary);
  const showAssistantPlaceholder =
    orderedNodeIds.length === 0 && !runError && state.isRunning;

  return (
    <section
      aria-label="Run observer"
      className="flex flex-col gap-4 text-ink"
    >
      <HumanTurn summary={summary} />

      {orderedNodeIds.map((nodeId) => {
        const node = state.nodes[nodeId];

        if (!node) {
          return null;
        }

        return (
          <AssistantTurn
            key={nodeId}
            nodeId={nodeId}
            text={node.streamText}
            status={node.status}
            error={node.error}
            isRunning={state.isRunning && node.status === "running"}
          />
        );
      })}

      {showAssistantPlaceholder ? <AssistantPlaceholder /> : null}

      {runError ? <AssistantError message={runError} /> : null}

      <RunFootnote summary={summary} state={state} />
    </section>
  );
}

function HumanTurn({ summary }: { summary: RunSummary }) {
  const text = `请对 SOP \`${summary.subject_id}\` 执行一次质量检查。`;

  return (
    <div className="flex justify-end">
      <p className="ml-auto max-w-[85%] whitespace-pre-wrap rounded-3xl bg-primary px-4 py-2 text-sm text-on-primary shadow-sm">
        {text}
      </p>
    </div>
  );
}

function AssistantTurn({
  nodeId,
  text,
  status,
  error,
  isRunning,
}: {
  nodeId: string;
  text: string;
  status: string;
  error?: string;
  isRunning: boolean;
}) {
  const hasText = text.trim().length > 0;

  return (
    <article
      aria-label={`Assistant turn ${nodeId}`}
      className="mr-auto flex w-full max-w-full flex-col gap-1"
    >
      <header className="flex items-center gap-2 text-xs text-mute">
        <span className="font-mono">{nodeId}</span>
        <NodeStatusChip status={status} isRunning={isRunning} />
      </header>
      <div className="text-sm text-ink">
        {hasText ? (
          <StreamMarkdown isStreaming={isRunning}>{text}</StreamMarkdown>
        ) : isRunning ? (
          <TypingIndicator />
        ) : status === "error" ? null : (
          <p className="text-mute">暂无输出。</p>
        )}
        {error ? (
          <p className="mt-1 text-sm text-error-deep">{error}</p>
        ) : null}
      </div>
    </article>
  );
}

function AssistantPlaceholder() {
  return (
    <article
      aria-label="Assistant turn pending"
      className="mr-auto flex w-full max-w-full flex-col gap-1"
    >
      <header className="flex items-center gap-2 text-xs text-mute">
        <span className="font-mono">助手</span>
      </header>
      <TypingIndicator />
    </article>
  );
}

function AssistantError({ message }: { message: string }) {
  return (
    <article
      aria-label="Assistant turn error"
      className="mr-auto flex w-full max-w-full flex-col gap-1"
      role="alert"
    >
      <header className="flex items-center gap-2 text-xs text-error-deep">
        <span className="font-mono">运行失败</span>
      </header>
      <p className="m-0 text-sm text-error-deep">{message}</p>
    </article>
  );
}

function NodeStatusChip({
  status,
  isRunning,
}: {
  status: string;
  isRunning: boolean;
}) {
  if (isRunning) {
    return <span className="text-primary">流式输出中</span>;
  }

  if (status === "done") {
    return <span className="text-mute">已完成</span>;
  }

  if (status === "error") {
    return <span className="text-error-deep">失败</span>;
  }

  if (status === "interrupted") {
    return <span className="text-error-deep">已中断</span>;
  }

  if (status === "idle") {
    return <span className="text-mute">等待中</span>;
  }

  if (status === "running") {
    return <span className="text-primary">运行中</span>;
  }

  return <span className="text-mute">{status}</span>;
}

function TypingIndicator() {
  return (
    <span
      aria-label="streaming"
      className="inline-flex items-center gap-1 text-mute"
    >
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary/70" />
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary/70 [animation-delay:120ms]" />
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary/70 [animation-delay:240ms]" />
    </span>
  );
}

function RunFootnote({
  summary,
  state,
}: {
  summary: RunSummary;
  state: RunViewState;
}) {
  const parts: string[] = [statusLabel(summary.status)];

  if (summary.finished_at) {
    parts.push(new Date(summary.finished_at).toLocaleString());
  } else if (summary.started_at) {
    parts.push(new Date(summary.started_at).toLocaleString());
  }

  if (state.isRunning && state.connectionStatus !== "open") {
    parts.push(connectionLabel(state.connectionStatus));
  }

  return (
    <p className="mt-1 text-xs text-mute">
      {parts.filter(Boolean).join(" · ")}
    </p>
  );
}

function statusLabel(status: string): string {
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
      return status;
  }
}

function connectionLabel(status: string): string {
  switch (status) {
    case "idle":
      return "等待连接";
    case "connecting":
      return "连接中";
    case "reconnecting":
      return "重新连接中";
    case "closed":
      return "已断开";
    default:
      return status;
  }
}

function collectRunError(
  state: RunViewState,
  summary: RunSummary,
): string | undefined {
  if (summary.error_summary) {
    return summary.error_summary;
  }

  for (let index = state.events.length - 1; index >= 0; index -= 1) {
    const event = state.events[index];

    if (event.type === "error" && !event.node) {
      const message = event.payload.error ?? event.payload.message;
      if (typeof message === "string") {
        return message;
      }
    }
  }

  return undefined;
}
