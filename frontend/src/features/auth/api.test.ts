// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";

import { devLogin, getCurrentUser, logout } from "./api";
import type { CurrentUser } from "./types";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("auth API", () => {
  it("gets current user", async () => {
    const user = buildUser({ account: "admin", is_admin: true });
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(user));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getCurrentUser()).resolves.toEqual(user);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/me",
      expect.objectContaining({ credentials: "same-origin" }),
    );
  });

  it("posts selected dev account", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          account: "admin",
          id: crypto.randomUUID(),
          is_admin: true,
          meta: {},
        }),
        {
          headers: { "Content-Type": "application/json" },
          status: 200,
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await devLogin("admin");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/dev-login",
      expect.objectContaining({
        body: JSON.stringify({ account: "admin" }),
        credentials: "same-origin",
        method: "POST",
      }),
    );
  });

  it("posts logout", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);

    await expect(logout()).resolves.toEqual({});

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/logout",
      expect.objectContaining({
        credentials: "same-origin",
        method: "POST",
      }),
    );
  });
});

function buildUser(overrides: Partial<CurrentUser> = {}): CurrentUser {
  return {
    account: "user",
    id: "user-id",
    is_admin: false,
    meta: {},
    ...overrides,
  };
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}
