import { useEffect, useMemo, useRef, useState } from "react";

import { RunObserver } from "../../runs/components/RunObserver";
import { startSopQualityRun } from "../api";
import {
  type SopPreviewRequest,
  useSopEnvironments,
  useSopPreview,
  useSopRunHistory,
} from "../hooks";
import type { SopPreview, SopRunHistoryItem } from "../types";

type SopQualityPageProps = {
  initialSopId?: string;
  registeredNodeIds?: string[];
};

const DEFAULT_REGISTERED_NODE_IDS = [
  "load_sop",
  "check_steps",
  "summarize_result",
];

export function SopQualityPage({
  initialSopId = "release-checklist",
  registeredNodeIds = DEFAULT_REGISTERED_NODE_IDS,
}: SopQualityPageProps) {
  const [sopId, setSopId] = useState(initialSopId);
  const [selectedEnv, setSelectedEnv] = useState("");
  const [observedRunId, setObservedRunId] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [startMessage, setStartMessage] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);
  const [previewRequest, setPreviewRequest] =
    useState<SopPreviewRequest | null>(null);
  const activeFormRef = useRef({ selectedEnv, sopId });
  const startRequestRef = useRef(0);
  const environments = useSopEnvironments();
  const preview = useSopPreview(previewRequest);
  const history = useSopRunHistory(sopId, selectedEnv, historyRefreshKey);

  activeFormRef.current = { selectedEnv, sopId };

  useEffect(() => {
    if (!selectedEnv && environments.data.length > 0) {
      setSelectedEnv(environments.data[0].key);
    }
  }, [environments.data, selectedEnv]);

  const selectedEnvironmentName = useMemo(() => {
    const environment = environments.data.find((item) => item.key === selectedEnv);

    return environment
      ? `${environment.name_en} (${environment.key})`
      : "Select environment";
  }, [environments.data, selectedEnv]);

  async function handleStartRun() {
    if (!sopId || !selectedEnv) {
      return;
    }

    const requestId = startRequestRef.current + 1;
    const requestSopId = sopId;
    const requestEnv = selectedEnv;

    startRequestRef.current = requestId;
    setStarting(true);
    setStartError(null);
    setStartMessage(null);

    try {
      const result = await startSopQualityRun(requestSopId, requestEnv);

      if (
        startRequestRef.current !== requestId ||
        activeFormRef.current.sopId !== requestSopId ||
        activeFormRef.current.selectedEnv !== requestEnv
      ) {
        return;
      }

      setObservedRunId(result.runId);
      setHistoryRefreshKey((value) => value + 1);

      if (result.kind === "active") {
        setStartMessage(`An active run already exists. Joined ${result.runId}.`);
      }
    } catch (error) {
      if (startRequestRef.current !== requestId) {
        return;
      }

      setStartError(error instanceof Error ? error.message : "Unable to start run.");
    } finally {
      if (startRequestRef.current === requestId) {
        setStarting(false);
      }
    }
  }

  function handlePreview() {
    if (!sopId || !selectedEnv) {
      return;
    }

    setPreviewRequest((current) => ({
      envKey: selectedEnv,
      requestId: (current?.requestId ?? 0) + 1,
      sopId,
    }));
  }

  function handleSopIdChange(nextSopId: string) {
    startRequestRef.current += 1;
    setSopId(nextSopId);
    setObservedRunId(null);
    setPreviewRequest(null);
    setStartError(null);
    setStartMessage(null);
    setStarting(false);
  }

  function handleEnvironmentChange(nextEnv: string) {
    startRequestRef.current += 1;
    setSelectedEnv(nextEnv);
    setObservedRunId(null);
    setPreviewRequest(null);
    setStartError(null);
    setStartMessage(null);
    setStarting(false);
  }

  return (
    <main className="min-h-screen bg-[#ffffff] px-4 py-5 text-[#212121] sm:px-6 lg:px-8">
      <div className="mx-auto grid max-w-6xl gap-4 lg:grid-cols-[320px_1fr]">
        <section className="space-y-3 rounded-lg border border-[#e5e7eb] bg-[#eeece7] p-4">
          <div className="border-b border-[#d9d9dd] pb-3">
            <p className="text-xs uppercase tracking-[0.08em] text-[#75758a]">
              SOP quality
            </p>
            <h1 className="mt-1 text-xl font-normal text-[#17171c]">
              Run workspace
            </h1>
          </div>

          <label className="block text-sm text-[#616161]" htmlFor="sop-id">
            SOP id
          </label>
          <input
            className="w-full rounded border border-[#d9d9dd] bg-white px-3 py-2 text-sm text-[#212121] outline-none focus:border-[#9b60aa] focus:ring-2 focus:ring-[#9b60aa]/20"
            id="sop-id"
            onChange={(event) => handleSopIdChange(event.target.value)}
            value={sopId}
          />

          <label className="block text-sm text-[#616161]" htmlFor="sop-env">
            Environment
          </label>
          <select
            aria-label="Environment"
            className="w-full rounded border border-[#d9d9dd] bg-white px-3 py-2 text-sm text-[#212121] outline-none focus:border-[#9b60aa] focus:ring-2 focus:ring-[#9b60aa]/20"
            disabled={environments.loading || environments.data.length === 0}
            id="sop-env"
            onChange={(event) => handleEnvironmentChange(event.target.value)}
            value={selectedEnv}
          >
            {environments.data.map((environment) => (
              <option key={environment.key} value={environment.key}>
                {environment.name_en} ({environment.key})
              </option>
            ))}
          </select>

          <button
            className="w-full rounded-lg border border-[#d9d9dd] bg-white px-3 py-2 text-sm font-medium text-[#17171c] disabled:cursor-not-allowed disabled:text-[#93939f]"
            disabled={!sopId || !selectedEnv || preview.loading}
            onClick={handlePreview}
            type="button"
          >
            {preview.loading ? "Loading preview" : "Preview SOP"}
          </button>

          <button
            className="w-full rounded-lg bg-[#17171c] px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-[#93939f]"
            disabled={!sopId || !selectedEnv || starting}
            onClick={handleStartRun}
            type="button"
          >
            {starting ? "Starting" : "Start run"}
          </button>

          {startError ? (
            <p
              className="rounded border border-[#b30000]/25 bg-white px-3 py-2 text-sm text-[#b30000]"
              role="alert"
            >
              {startError}
            </p>
          ) : null}

          {startMessage ? (
            <p
              className="rounded border border-[#1863dc]/25 bg-white px-3 py-2 text-sm text-[#1863dc]"
              role="status"
            >
              {startMessage}
            </p>
          ) : null}

          <section
            aria-label="SOP preview"
            className="rounded-lg border border-[#e5e7eb] bg-white p-3"
          >
            <div className="flex items-center justify-between gap-3 border-b border-[#f2f2f2] pb-2">
              <h2 className="text-sm font-medium text-[#17171c]">Preview</h2>
              <span className="text-xs text-[#75758a]">{selectedEnvironmentName}</span>
            </div>
            <SopPreviewPanel
              error={preview.error}
              preview={preview.data}
              loading={preview.loading}
            />
          </section>

          <section
            aria-label="Run history"
            className="rounded-lg border border-[#e5e7eb] bg-white p-3"
          >
            <div className="flex items-center justify-between gap-3 border-b border-[#f2f2f2] pb-2">
              <h2 className="text-sm font-medium text-[#17171c]">History</h2>
              {history.loading ? (
                <span className="text-xs text-[#75758a]">Loading</span>
              ) : null}
            </div>
            <RunHistory
              observedRunId={observedRunId}
              onSelectRun={setObservedRunId}
              runs={history.data}
            />
          </section>
        </section>

        <section className="rounded-lg border border-[#e5e7eb] bg-white p-4">
          {observedRunId ? (
            <RunObserver
              runId={observedRunId}
              registeredNodeIds={registeredNodeIds}
            />
          ) : (
            <div className="rounded border border-[#f2f2f2] px-4 py-6 text-sm text-[#616161]">
              Select a history run or start a new quality run.
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function SopPreviewPanel({
  error,
  loading,
  preview,
}: {
  error: Error | null;
  loading: boolean;
  preview: SopPreview | null;
}) {
  if (loading) {
    return <p className="pt-3 text-sm text-[#616161]">Loading preview</p>;
  }

  if (error) {
    return (
      <p className="pt-3 text-sm text-[#b30000]" role="alert">
        {error.message}
      </p>
    );
  }

  if (!preview) {
    return <p className="pt-3 text-sm text-[#616161]">No preview loaded.</p>;
  }

  return (
    <div className="space-y-2 pt-3">
      <p className="text-sm font-medium text-[#212121]">
        {getPreviewTitle(preview)}
      </p>
      <pre className="max-h-56 overflow-auto rounded border border-[#f2f2f2] bg-[#ffffff] p-2 text-xs leading-5 text-[#616161]">
        {JSON.stringify(preview.raw_payload ?? preview, null, 2)}
      </pre>
    </div>
  );
}

function RunHistory({
  observedRunId,
  onSelectRun,
  runs,
}: {
  observedRunId: string | null;
  onSelectRun: (runId: string) => void;
  runs: SopRunHistoryItem[];
}) {
  if (runs.length === 0) {
    return <p className="pt-3 text-sm text-[#616161]">No runs yet.</p>;
  }

  return (
    <ul className="space-y-2 pt-3">
      {runs.map((run) => (
        <li key={run.run_id}>
          <button
            aria-pressed={observedRunId === run.run_id}
            className="w-full rounded border border-[#e5e7eb] px-3 py-2 text-left text-sm text-[#212121] hover:border-[#d9d9dd] aria-pressed:border-[#17171c]"
            onClick={() => onSelectRun(run.run_id)}
            type="button"
          >
            <span className="block font-medium">{run.run_id}</span>
            <span className="mt-1 block text-xs text-[#75758a]">
              {[run.status, formatCreatedAt(run.created_at)]
                .filter(Boolean)
                .join(" / ")}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

function getPreviewTitle(preview: SopPreview): string {
  const payload = isRecord(preview.raw_payload) ? preview.raw_payload : preview;
  const title = payload.title;

  return typeof title === "string" && title ? title : "SOP preview";
}

function formatCreatedAt(value: string | null | undefined): string {
  if (!value) {
    return "";
  }

  return new Date(value).toLocaleString();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
