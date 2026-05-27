import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { devLogin, getCurrentUser, logout as logoutRequest } from "./api";
import type { CurrentUser } from "./types";

export type AuthState =
  | { status: "loading"; user: null }
  | { status: "anonymous"; user: null }
  | { status: "authenticated"; user: CurrentUser };

type AuthContextValue = AuthState & {
  refresh: () => Promise<void>;
  loginAs: (account: string) => Promise<CurrentUser>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    status: "loading",
    user: null,
  });
  const mountedRef = useRef(true);
  const requestIdRef = useRef(0);

  useEffect(() => {
    mountedRef.current = true;

    return () => {
      mountedRef.current = false;
    };
  }, []);

  const refresh = useCallback(async () => {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setState({ status: "loading", user: null });

    try {
      const user = await getCurrentUser();

      if (!mountedRef.current || requestIdRef.current !== requestId) {
        return;
      }

      setState({ status: "authenticated", user });
    } catch {
      if (!mountedRef.current || requestIdRef.current !== requestId) {
        return;
      }

      setState({ status: "anonymous", user: null });
    }
  }, []);

  const loginAs = useCallback(async (account: string) => {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    const user = await devLogin(account);

    if (mountedRef.current && requestIdRef.current === requestId) {
      setState({ status: "authenticated", user });
    }

    return user;
  }, []);

  const logout = useCallback(async () => {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;

    await logoutRequest();

    if (mountedRef.current && requestIdRef.current === requestId) {
      setState({ status: "anonymous", user: null });
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      loginAs,
      logout,
      refresh,
    }),
    [loginAs, logout, refresh, state],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);

  if (!value) {
    throw new Error("useAuth must be used within AuthProvider");
  }

  return value;
}
