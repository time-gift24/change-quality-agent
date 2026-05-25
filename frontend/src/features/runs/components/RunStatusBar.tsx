import type { RunSummary } from "../types";

type RunStatusBarProps = {
  summary: RunSummary;
  connectionStatus?: string;
};

export function RunStatusBar({
  summary,
  connectionStatus,
}: RunStatusBarProps) {
  const metadata = [
    ["Status", summary.status],
    ["Subject", summary.subject_type],
    ["Subject ID", summary.subject_id],
    ["Current node", summary.current_node],
    ["Started", summary.started_at],
    ["Finished", summary.finished_at],
    ["Result", summary.result_status],
  ].filter(([, value]) => value !== undefined && value !== null && value !== "");

  return (
    <section
      aria-label="Run status"
      className="rounded-lg border border-[#e5e7eb] bg-white"
    >
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-[#e5e7eb] px-4 py-3">
        {metadata.map(([label, value]) => (
          <div className="min-w-0 text-sm" key={label}>
            <span className="text-xs text-[#616161]">{label}</span>{" "}
            <span className="font-medium text-[#212121]">{value}</span>
          </div>
        ))}
        {connectionStatus ? (
          <div className="text-sm">
            <span className="text-xs text-[#616161]">Connection</span>{" "}
            <span className="font-medium text-[#212121]">
              {connectionStatus}
            </span>
          </div>
        ) : null}
      </div>
      {summary.error_summary ? (
        <div className="border-b border-[#e5e7eb] px-4 py-2 text-sm text-[#b30000]">
          {summary.error_summary}
        </div>
      ) : null}
    </section>
  );
}
