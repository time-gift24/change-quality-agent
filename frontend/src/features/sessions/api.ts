import { requestJson } from "../../lib/apiClient";
import type { SessionDetail, SessionMessage } from "./types";

export function getSession(sessionId: number): Promise<SessionDetail> {
  return requestJson<SessionDetail>(
    `/api/sessions/${encodeURIComponent(sessionId)}`,
  );
}

export function getSessionMessages(
  sessionId: number,
  after = 0,
): Promise<SessionMessage[]> {
  return requestJson<SessionMessage[]>(
    `/api/sessions/${encodeURIComponent(sessionId)}/messages?after=${after}`,
  );
}

export function buildSessionStreamUrl(
  sessionId: number,
  after = 0,
): string {
  return `/api/sessions/${encodeURIComponent(sessionId)}/stream?after=${after}`;
}
