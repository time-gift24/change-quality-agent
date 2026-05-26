import type { McpServerRuntimeStatus } from "../types";

type McpStatusBadgeProps = {
  status: McpServerRuntimeStatus;
};

const STATUS_STYLES: Record<McpServerRuntimeStatus, { pill: string; text: string; dot: string }> = {
  running: {
    pill: "bg-success/15",
    text: "text-success",
    dot: "bg-success",
  },
  stopped: {
    pill: "bg-canvas-soft border border-hairline",
    text: "text-body",
    dot: "bg-hairline-strong",
  },
  error: {
    pill: "bg-error-soft",
    text: "text-error-deep",
    dot: "bg-error",
  },
  starting: {
    pill: "bg-primary-soft",
    text: "text-primary-deep",
    dot: "bg-primary",
  },
  stopping: {
    pill: "bg-primary-soft",
    text: "text-primary-deep",
    dot: "bg-primary",
  },
  unknown: {
    pill: "bg-canvas-soft border border-hairline",
    text: "text-mute",
    dot: "bg-hairline-strong",
  },
};

export function McpStatusBadge({ status }: McpStatusBadgeProps) {
  const style = STATUS_STYLES[status];

  return (
    <span
      className={`inline-flex h-4 items-center gap-1 rounded-full px-1.5 text-2xs font-medium ${style.pill} ${style.text}`}
    >
      <span
        aria-hidden="true"
        className={`inline-block h-1 w-1 shrink-0 rounded-full ${style.dot}`}
        data-status={status}
        data-testid="status-dot"
      />
      {status}
    </span>
  );
}
