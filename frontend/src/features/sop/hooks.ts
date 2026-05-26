import { useEffect, useState } from "react";

import { getSopEnvironments, getSopRunHistory } from "./api";
import type { SopEnvironment, SopRunHistoryItem } from "./types";

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

export function useSopRunHistory(
  sopId: string,
  envKey: string,
  refreshKey = 0,
): AsyncState<SopRunHistoryItem[]> {
  const [state, setState] = useState<AsyncState<SopRunHistoryItem[]>>({
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
    getSopRunHistory(sopId, envKey)
      .then((runs) => {
        if (!cancelled) {
          setState({ data: runs, error: null, loading: false });
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
