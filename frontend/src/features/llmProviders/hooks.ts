import { useCallback, useEffect, useRef, useState } from "react";

import {
  createLlmProvider,
  deleteLlmProvider,
  getLlmProvider,
  listLlmProviders,
  updateLlmProvider,
} from "./api";
import type {
  LlmProviderCreate,
  LlmProviderDetail,
  LlmProviderSummary,
  LlmProviderUpdate,
} from "./types";

type AsyncState<T> = {
  data: T;
  error: Error | null;
  loading: boolean;
};

type AsyncStateWithRefetch<T> = AsyncState<T> & {
  refetch: () => Promise<void>;
};

type MutationOptions<TResult> = {
  onSuccess?: (result: TResult) => void | Promise<void>;
};

export function useLlmProviders(): AsyncStateWithRefetch<LlmProviderSummary[]> {
  const [state, setState] = useState<AsyncState<LlmProviderSummary[]>>({
    data: [],
    error: null,
    loading: true,
  });
  const mountedRef = useRef(true);
  const requestIdRef = useRef(0);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const refetch = useCallback(async () => {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setState((current) => ({ ...current, error: null, loading: true }));

    try {
      const providers = await listLlmProviders();
      if (!mountedRef.current || requestIdRef.current !== requestId) return;
      setState({ data: providers, error: null, loading: false });
    } catch (error) {
      if (!mountedRef.current || requestIdRef.current !== requestId) return;
      setState({ data: [], error: asError(error), loading: false });
    }
  }, []);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  return { ...state, refetch };
}

export function useLlmProviderDetail(
  providerId: string | null | undefined,
): AsyncStateWithRefetch<LlmProviderDetail | null> {
  const [state, setState] = useState<AsyncState<LlmProviderDetail | null>>({
    data: null,
    error: null,
    loading: false,
  });
  const mountedRef = useRef(true);
  const requestIdRef = useRef(0);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const refetch = useCallback(async () => {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;

    if (!providerId) {
      setState({ data: null, error: null, loading: false });
      return;
    }

    setState({ data: null, error: null, loading: true });

    try {
      const provider = await getLlmProvider(providerId);
      if (!mountedRef.current || requestIdRef.current !== requestId) return;
      setState({ data: provider, error: null, loading: false });
    } catch (error) {
      if (!mountedRef.current || requestIdRef.current !== requestId) return;
      setState({ data: null, error: asError(error), loading: false });
    }
  }, [providerId]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  return { ...state, refetch };
}

export function useLlmProviderMutations() {
  const [pendingCount, setPendingCount] = useState(0);
  const [error, setError] = useState<Error | null>(null);

  const runMutation = useCallback(
    async <TResult,>(
      action: () => Promise<TResult>,
      options?: MutationOptions<TResult>,
    ): Promise<TResult> => {
      setPendingCount((current) => current + 1);
      setError(null);
      try {
        const result = await action();
        await options?.onSuccess?.(result);
        return result;
      } catch (mutationError) {
        const nextError = asError(mutationError);
        setError(nextError);
        throw nextError;
      } finally {
        setPendingCount((current) => Math.max(0, current - 1));
      }
    },
    [],
  );

  return {
    createProvider: (
      payload: LlmProviderCreate,
      options?: MutationOptions<LlmProviderDetail>,
    ) => runMutation(() => createLlmProvider(payload), options),
    deleteProvider: (providerId: string, options?: MutationOptions<void>) =>
      runMutation(() => deleteLlmProvider(providerId), options),
    error,
    pending: pendingCount > 0,
    updateProvider: (
      providerId: string,
      payload: LlmProviderUpdate,
      options?: MutationOptions<LlmProviderDetail>,
    ) => runMutation(() => updateLlmProvider(providerId, payload), options),
  };
}

function asError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error));
}
