import { useEffect, useRef } from "react";

import { useSopQualityCheck } from "../hooks";
import {
  getOrderedNodeIds,
  type SopQualityCheckViewState,
} from "../reducer";
import type { SopQualityCheckDetail } from "../types";
import { StreamMarkdown } from "./StreamMarkdown";

type Props = {
  checkId: string;
  registeredNodeIds?: string[];
};

const DEFAULT_REGISTERED_NODE_IDS = [
  "load_sop",
  "check_steps",
  "summarize_result",
];

const NODE_LABELS: Record<string, string> = {
  load_sop: "读取 SOP",
  check_steps: "检查步骤",
  summarize_result: "生成总结",
};

export function SopQualityCheckObserver({
  checkId,
  registeredNodeIds = DEFAULT_REGISTERED_NODE_IDS,
}: Props) {
  const { detail, error, loading, state } = useSopQualityCheck(checkId);

  if (error) {
    return (
      <section
        aria-label="SOP quality check observer"
        className="rounded-2xl border border-hairline bg-canvas px-4 py-3 text-sm text-error-deep"
        role="alert"
      >
        {error.message}
      </section>
    );
  }

  if (!detail) {
    return (
      <section
        aria-label="SOP quality check observer"
        className="rounded-2xl border border-hairline bg-canvas px-4 py-3 text-sm text-body"
      >
        {loading ? "正在加载质检..." : "质检不存在或已过期。"}
      </section>
    );
  }

  return (
    <SopQualityCheckObserverView
      detail={detail}
      state={state}
      registeredNodeIds={registeredNodeIds}
    />
  );
}

export function SopQualityCheckObserverView({
  detail,
  state,
  registeredNodeIds = DEFAULT_REGISTERED_NODE_IDS,
}: {
  detail: SopQualityCheckDetail;
  state: SopQualityCheckViewState;
  registeredNodeIds?: string[];
}) {
  const orderedNodeIds = getOrderedNodeIds(state, registeredNodeIds);
  const checkError = collectCheckError(state, detail);
  const showAssistantPlaceholder =
    orderedNodeIds.length === 0 && !checkError && state.isRunning;
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const bottom = bottomRef.current;
    if (!bottom) {
      return;
    }

    scrollToBottom(bottom);
    const animationFrame = window.requestAnimationFrame(() => {
      scrollToBottom(bottom);
    });
    const timeout = window.setTimeout(() => {
      scrollToBottom(bottom);
    }, 50);

    return () => {
      window.cancelAnimationFrame(animationFrame);
      window.clearTimeout(timeout);
    };
  }, [detail.check_id, state.latestSequence]);

  return (
    <section
      aria-label="SOP quality check observer"
      className="flex flex-col gap-4 text-ink"
    >
      <HumanTurn detail={detail} />

      {orderedNodeIds.map((nodeId) => {
        const node = state.nodes[nodeId];
        if (!node) {
          return null;
        }

        return (
          <AssistantTurn
            key={nodeId}
            nodeId={nodeId}
            label={nodeLabel(nodeId)}
            text={node.streamText}
            thinkingText={node.thinkingText}
            status={node.status}
            error={node.error}
            isRunning={state.isRunning && node.status === "running"}
          />
        );
      })}

      {showAssistantPlaceholder ? <AssistantPlaceholder /> : null}
      {checkError ? <AssistantError message={checkError} /> : null}

      <ObserverFootnote detail={detail} state={state} />
      <div aria-hidden="true" className="h-px" ref={bottomRef} />
    </section>
  );
}

function HumanTurn({ detail }: { detail: SopQualityCheckDetail }) {
  const text = `请对 SOP \`${detail.sop_id}\` 执行一次质量检查。`;

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
  label,
  text,
  thinkingText,
  status,
  error,
  isRunning,
}: {
  nodeId: string;
  label: string;
  text: string;
  thinkingText?: string;
  status: string;
  error?: string;
  isRunning: boolean;
}) {
  const hasText = text.trim().length > 0;
  const hasThinkingText = Boolean(thinkingText?.trim());

  return (
    <article
      aria-label={`Assistant turn ${nodeId}`}
      className="mr-auto flex w-full max-w-full flex-col gap-1"
    >
      <header className="flex items-center gap-2 text-xs text-mute">
        <span>{label}</span>
        <NodeStatusChip status={status} isRunning={isRunning} />
      </header>
      <div className="text-sm text-ink">
        {hasThinkingText ? <ThinkingBlock text={thinkingText ?? ""} /> : null}
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

function ThinkingBlock({ text }: { text: string }) {
  return (
    <div className="mb-2 border-l-2 border-primary/30 pl-3 text-xs text-mute">
      <div className="font-medium text-body">思考</div>
      <p className="mt-1 whitespace-pre-wrap">{text}</p>
    </div>
  );
}

function nodeLabel(nodeId: string): string {
  return NODE_LABELS[nodeId] ?? nodeId;
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
        <span className="font-mono">质检失败</span>
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

function ObserverFootnote({
  detail,
  state,
}: {
  detail: SopQualityCheckDetail;
  state: SopQualityCheckViewState;
}) {
  const parts: string[] = [statusLabel(detail.status)];

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
    case "succeeded":
      return "成功";
    case "failed":
      return "失败";
    case "cancelled":
      return "已取消";
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

function collectCheckError(
  state: SopQualityCheckViewState,
  detail: SopQualityCheckDetail,
): string | undefined {
  if (typeof detail.error?.message === "string") {
    return detail.error.message;
  }

  for (let index = state.events.length - 1; index >= 0; index -= 1) {
    const event = state.events[index];
    if (event.type === "failed" && !event.node && event.message) {
      return event.message;
    }
  }

  return undefined;
}

function scrollToBottom(target: HTMLElement): void {
  const scrollParent = findScrollParent(target);
  if (scrollParent) {
    scrollParent.scrollTop = scrollParent.scrollHeight;
    return;
  }

  const scrollIntoView = target.scrollIntoView;
  if (typeof scrollIntoView === "function") {
    scrollIntoView.call(target, {
      block: "end",
      behavior: "smooth",
    });
  }
}

function findScrollParent(target: HTMLElement): HTMLElement | null {
  let parent = target.parentElement;
  while (parent) {
    const overflowY = window.getComputedStyle(parent).overflowY;
    if (overflowY === "auto" || overflowY === "scroll") {
      return parent;
    }
    parent = parent.parentElement;
  }
  return null;
}
