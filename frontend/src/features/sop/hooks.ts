import { useEffect, useState } from "react";

import {
  getRecentSopQualityChecks,
  getSopEnvironments,
  getSopQualityCheckHistory,
} from "./api";
import type { SopEnvironment, SopQualityCheckHistoryItem } from "./types";

type AsyncState<T> = {
  data: T;
  error: Error | null;
  loading: boolean;
};

export function useSopEnvironments(): AsyncState<SopEnvironment[]> {
  const [state, setState] = useState<AsyncState<SopEnvironment[]>>({
    data: [],
    error: null,
    loading: true,
  });

  useEffect(() => {
    let cancelled = false;

    setState((current) => ({ ...current, error: null, loading: true }));
    getSopEnvironments()
      .then((environments) => {
        if (!cancelled) {
          setState({ data: environments, error: null, loading: false });
        }
      })
      .catch((error: Error) => {
        if (!cancelled) {
          setState({ data: [], error, loading: false });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}

export function useSopQualityCheckHistory(
  sopId: string,
  envKey: string,
  refreshKey = 0,
): AsyncState<SopQualityCheckHistoryItem[]> {
  const [state, setState] = useState<
    AsyncState<SopQualityCheckHistoryItem[]>
  >({
    data: [],
    error: null,
    loading: false,
  });

  useEffect(() => {
    if (!sopId || !envKey) {
      setState({ data: [], error: null, loading: false });
      return;
    }

    let cancelled = false;

    setState({ data: [], error: null, loading: true });
    getSopQualityCheckHistory(sopId, envKey)
      .then((checks) => {
        if (!cancelled) {
          setState({ data: checks, error: null, loading: false });
        }
      })
      .catch((error: Error) => {
        if (!cancelled) {
          setState({ data: [], error, loading: false });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [envKey, refreshKey, sopId]);

  return state;
}

export function useRecentSopQualityChecks(
  envKey: string,
  refreshKey = 0,
): AsyncState<SopQualityCheckHistoryItem[]> {
  const [state, setState] = useState<
    AsyncState<SopQualityCheckHistoryItem[]>
  >({
    data: [],
    error: null,
    loading: false,
  });

  useEffect(() => {
    if (!envKey) {
      setState({ data: [], error: null, loading: false });
      return;
    }

    let cancelled = false;

    setState({ data: [], error: null, loading: true });
    getRecentSopQualityChecks(envKey)
      .then((checks) => {
        if (!cancelled) {
          setState({ data: checks, error: null, loading: false });
        }
      })
      .catch((error: Error) => {
        if (!cancelled) {
          setState({ data: [], error, loading: false });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [envKey, refreshKey]);

  return state;
}
