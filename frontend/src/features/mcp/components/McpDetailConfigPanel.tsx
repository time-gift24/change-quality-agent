import type { McpServerDetail } from "../types";

type McpDetailConfigPanelProps = {
  server: McpServerDetail;
};

function ConfigRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="grid grid-cols-[160px_minmax(0,1fr)] gap-3 border-b border-hairline px-4 py-2.5 last:border-0">
      <dt className="text-2xs uppercase tracking-wide text-mute font-mono">{label}</dt>
      <dd className={`text-xs text-ink break-all ${mono ? "font-mono text-2xs" : ""}`}>
        {value}
      </dd>
    </div>
  );
}

function MultiConfigRow({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="grid grid-cols-[160px_minmax(0,1fr)] gap-3 border-b border-hairline px-4 py-2.5 last:border-0">
      <dt className="text-2xs uppercase tracking-wide text-mute font-mono">{label}</dt>
      <dd className="space-y-0.5">
        {values.length === 0
          ? <span className="text-xs text-mute">-</span>
          : values.map((v, i) => (
              <div key={i} className="font-mono text-2xs text-ink break-all">{v}</div>
            ))}
      </dd>
    </div>
  );
}

export function McpDetailConfigPanel({ server }: McpDetailConfigPanelProps) {
  const envLines = Object.entries(server.env).map(([k, v]) => `${k}=${v}`);
  const headerLines = Object.entries(server.headers).map(([k, v]) => `${k}=${v}`);

  return (
    <div className="rounded-xl border border-hairline bg-canvas">
      {server.last_error ? (
        <p
          role="alert"
          className="rounded-t-xl border-b border-error-soft bg-canvas px-3 py-2 text-xs text-error-deep"
        >
          {server.last_error}
        </p>
      ) : null}

      <dl>
        <ConfigRow label="Transport" value={server.transport} />
        {server.transport === "stdio" ? (
          <ConfigRow label="Command" value={server.command ?? "-"} mono />
        ) : (
          <ConfigRow label="URL" value={server.url ?? "-"} mono />
        )}
        <ConfigRow label="Args" value={server.args.length > 0 ? server.args.join(" ") : "-"} mono />
        <ConfigRow label="Enabled" value={server.enabled ? "true" : "false"} />
        <ConfigRow label="Desired State" value={server.desired_state} />
        <MultiConfigRow label="Env" values={envLines} />
        <MultiConfigRow label="Headers" values={headerLines} />
      </dl>
    </div>
  );
}
