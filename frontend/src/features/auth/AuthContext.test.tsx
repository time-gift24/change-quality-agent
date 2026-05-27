// @vitest-environment jsdom

import { type ReactNode } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { devLogin, getCurrentUser, logout as logoutRequest } from "./api";
import { AuthProvider, useAuth } from "./AuthContext";
import type { CurrentUser } from "./types";

vi.mock("./api", () => ({
  devLogin: vi.fn(),
  getCurrentUser: vi.fn(),
  logout: vi.fn(),
}));

describe("AuthContext", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads the current user on initial render", async () => {
    const user = buildUser({ account: "admin", is_admin: true });
    vi.mocked(getCurrentUser).mockResolvedValueOnce(user);

    const { result } = renderHook(() => useAuth(), { wrapper: AuthWrapper });

    expect(result.current.status).toBe("loading");
    expect(result.current.user).toBeNull();

    await waitFor(() => {
      expect(result.current.status).toBe("authenticated");
    });

    expect(result.current.user).toEqual(user);
    expect(getCurrentUser).toHaveBeenCalledTimes(1);
  });

  it("uses anonymous state when current user lookup fails", async () => {
    vi.mocked(getCurrentUser).mockRejectedValueOnce(new Error("not logged in"));

    const { result } = renderHook(() => useAuth(), { wrapper: AuthWrapper });

    await waitFor(() => {
      expect(result.current.status).toBe("anonymous");
    });

    expect(result.current.user).toBeNull();
  });

  it("updates state after dev login and logout", async () => {
    const user = buildUser({ account: "admin", is_admin: true });
    vi.mocked(getCurrentUser).mockRejectedValueOnce(new Error("not logged in"));
    vi.mocked(devLogin).mockResolvedValueOnce(user);
    vi.mocked(logoutRequest).mockResolvedValueOnce(undefined);

    const { result } = renderHook(() => useAuth(), { wrapper: AuthWrapper });

    await waitFor(() => {
      expect(result.current.status).toBe("anonymous");
    });

    await act(async () => {
      await result.current.loginAs("admin");
    });

    expect(devLogin).toHaveBeenCalledWith("admin");
    expect(result.current.status).toBe("authenticated");
    expect(result.current.user).toEqual(user);

    await act(async () => {
      await result.current.logout();
    });

    expect(logoutRequest).toHaveBeenCalledTimes(1);
    expect(result.current.status).toBe("anonymous");
    expect(result.current.user).toBeNull();
  });

  it("refreshes auth state on demand", async () => {
    const user = buildUser({ account: "reader" });
    vi.mocked(getCurrentUser)
      .mockRejectedValueOnce(new Error("not logged in"))
      .mockResolvedValueOnce(user);

    const { result } = renderHook(() => useAuth(), { wrapper: AuthWrapper });

    await waitFor(() => {
      expect(result.current.status).toBe("anonymous");
    });

    await act(async () => {
      await result.current.refresh();
    });

    expect(getCurrentUser).toHaveBeenCalledTimes(2);
    expect(result.current.status).toBe("authenticated");
    expect(result.current.user).toEqual(user);
  });
});

function AuthWrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

function buildUser(overrides: Partial<CurrentUser> = {}): CurrentUser {
  return {
    account: "user",
    id: "user-id",
    is_admin: false,
    meta: {},
    ...overrides,
  };
}
