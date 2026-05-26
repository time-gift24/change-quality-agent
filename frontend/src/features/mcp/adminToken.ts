export const MCP_ADMIN_TOKEN_STORAGE_KEY = "mcp-admin-token";

export function getMcpAdminToken(): string {
  const storage = getSessionStorage();

  return storage?.getItem(MCP_ADMIN_TOKEN_STORAGE_KEY)?.trim() ?? "";
}

export function setMcpAdminToken(token: string): void {
  const storage = getSessionStorage();

  if (!storage) {
    return;
  }

  const nextToken = token.trim();

  if (nextToken.length === 0) {
    storage.removeItem(MCP_ADMIN_TOKEN_STORAGE_KEY);
    return;
  }

  storage.setItem(MCP_ADMIN_TOKEN_STORAGE_KEY, nextToken);
}

export function clearMcpAdminToken(): void {
  getSessionStorage()?.removeItem(MCP_ADMIN_TOKEN_STORAGE_KEY);
}

function getSessionStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
}
