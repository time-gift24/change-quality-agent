import { requestJson } from "../../lib/apiClient";
import type { CurrentUser } from "./types";

export function getCurrentUser(): Promise<CurrentUser> {
  return requestJson<CurrentUser>("/api/auth/me");
}

export function devLogin(account: string): Promise<CurrentUser> {
  return requestJson<CurrentUser>("/api/auth/dev-login", {
    body: JSON.stringify({ account }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
}

export function logout(): Promise<void> {
  return requestJson<void>("/api/auth/logout", {
    method: "POST",
  });
}
