type AdminTokenControlProps = {
  value: string;
  saved: boolean;
  onChange: (next: string) => void;
  onSave: () => void;
};

export function AdminTokenControl({
  value,
  saved,
  onChange,
  onSave,
}: AdminTokenControlProps) {
  return (
    <div className="flex items-center gap-2">
      <input
        aria-label="MCP Admin Token"
        autoComplete="off"
        className="h-9 w-40 rounded-xl border border-hairline bg-canvas px-3 text-xs text-ink outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/25 sm:w-52"
        id="mcp-admin-token"
        onChange={(event) => onChange(event.target.value)}
        placeholder="X-MCP-Admin-Token"
        type="password"
        value={value}
      />
      <button
        className="h-9 shrink-0 rounded-xl border border-hairline bg-canvas px-3 text-xs font-medium text-body transition-colors hover:border-hairline-strong hover:text-ink"
        onClick={onSave}
        type="button"
      >
        保存 Token
      </button>
      {saved ? (
        <span className="text-2xs text-mute" role="status">
          已保存
        </span>
      ) : null}
    </div>
  );
}
