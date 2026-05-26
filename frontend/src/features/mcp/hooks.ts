import { useCallback, useEffect, useRef, useState } from "react";

import {
  checkMcpServer,
  createMcpServer,
  deleteMcpServer,
  getMcpServer,
  listMcpServers,
  restartMcpServer,
  startMcpServer,
  stopMcpServer,
  updateMcpServer,
} from "./api";
import type {
  McpLifecycleResponse,
  McpServerCreate,
  McpServerDetail,
  McpServerSummary,
  McpServerUpdate,
} from "./types";

type AsyncState<T> = {
  data: T;
  error: Error | null;
  loading: boolean;
};

type AsyncStateWithRefetch<T> = AsyncState<T> & {
  refetch: () => Promise<void>;
};

type MutationSuccessCallback<TResult> =
  | ((result: TResult) => void | Promise<void>)
  | undefined;

type MutationOptions<TResult> = {
  onSuccess?: MutationSuccessCallback<TResult>;
};

type UseMcpMutationsOptions = {
  onSuccess?: () => void | Promise<void>;
};

type UseMcpMutationsResult = {
  pending: boolean;
  error: Error | null;
  createServer: (
    payload: McpServerCreate,
    options?: MutationOptions<McpServerDetail>,
  ) => Promise<McpServerDetail>;
  updateServer: (
    serverId: string,
    payload: McpServerUpdate,
    options?: MutationOptions<McpServerDetail>,
  ) => Promise<McpServerDetail>;
  deleteServer: (
    serverId: string,
    options?: MutationOptions<void>,
  ) => Promise<void>;
  startServer: (
    serverId: string,
    options?: MutationOptions<McpLifecycleResponse>,
  ) => Promise<McpLifecycleResponse>;
  stopServer: (
    serverId: string,
    options?: MutationOptions<McpLifecycleResponse>,
  ) => Promise<McpLifecycleResponse>;
  restartServer: (
    serverId: string,
    options?: MutationOptions<McpLifecycleResponse>,
  ) => Promise<McpLifecycleResponse>;
  checkServer: (
    serverId: string,
    options?: MutationOptions<McpLifecycleResponse>,
  ) => Promise<McpLifecycleResponse>;
};

export function useMcpServers(): AsyncStateWithRefetch<McpServerSummary[]> {
  const [state, setState] = useState<AsyncState<McpServerSummary[]>>({
    data: [],
    error: null,
    loading: true,
  });
  const requestIdRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const refetch = useCallback(async () => {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;

    setState((current) => ({ ...current, error: null, loading: true }));

    try {
      const servers = await listMcpServers();

      if (!mountedRef.current || requestIdRef.current !== requestId) {
        return;
      }

      setState({ data: servers, error: null, loading: false });
    } catch (error) {
      if (!mountedRef.current || requestIdRef.current !== requestId) {
        return;
      }

      setState({ data: [], error: asError(error), loading: false });
    }
  }, []);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  return {
    ...state,
    refetch,
  };
}

export function useMcpServerDetail(
  serverId: string | null | undefined,
): AsyncStateWithRefetch<McpServerDetail | null> {
  const [state, setState] = useState<AsyncState<McpServerDetail | null>>({
    data: null,
    error: null,
    loading: false,
  });
  const requestIdRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const refetch = useCallback(async () => {
    if (!serverId) {
      setState({ data: null, error: null, loading: false });
      return;
    }

    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;

    setState((current) => ({ ...current, error: null, loading: true }));

    try {
      const detail = await getMcpServer(serverId);

      if (!mountedRef.current || requestIdRef.current !== requestId) {
        return;
      }

      setState({ data: detail, error: null, loading: false });
    } catch (error) {
      if (!mountedRef.current || requestIdRef.current !== requestId) {
        return;
      }

      setState({ data: null, error: asError(error), loading: false });
    }
  }, [serverId]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  return {
    ...state,
    refetch,
  };
}

export function useMcpMutations(
  options: UseMcpMutationsOptions = {},
): UseMcpMutationsResult {
  const { onSuccess } = options;
  const [pendingCount, setPendingCount] = useState(0);
  const [error, setError] = useState<Error | null>(null);

  const runMutation = useCallback(
    async <TResult,>(
      action: () => Promise<TResult>,
      mutationOptions?: MutationOptions<TResult>,
    ): Promise<TResult> => {
      setPendingCount((current) => current + 1);
      setError(null);

      try {
        const result = await action();
        let callbackError: Error | null = null;

        if (onSuccess) {
          try {
            await onSuccess();
          } catch (mutationSuccessError) {
            callbackError = asError(mutationSuccessError);
          }
        }

        if (mutationOptions?.onSuccess) {
          try {
            await mutationOptions.onSuccess(result);
          } catch (mutationSuccessError) {
            if (!callbackError) {
              callbackError = asError(mutationSuccessError);
            }
          }
        }

        if (callbackError) {
          setError(callbackError);
        }

        return result;
      } catch (mutationError) {
        const nextError = asError(mutationError);
        setError(nextError);
        throw nextError;
      } finally {
        setPendingCount((current) => Math.max(0, current - 1));
      }
    },
    [onSuccess],
  );

  const createServer = useCallback(
    (
      payload: McpServerCreate,
      mutationOptions?: MutationOptions<McpServerDetail>,
    ) => runMutation(() => createMcpServer(payload), mutationOptions),
    [runMutation],
  );

  const updateServer = useCallback(
    (
      serverId: string,
      payload: McpServerUpdate,
      mutationOptions?: MutationOptions<McpServerDetail>,
    ) => runMutation(() => updateMcpServer(serverId, payload), mutationOptions),
    [runMutation],
  );

  const deleteServer = useCallback(
    (serverId: string, mutationOptions?: MutationOptions<void>) =>
      runMutation(() => deleteMcpServer(serverId), mutationOptions),
    [runMutation],
  );

  const startServer = useCallback(
    (
      serverId: string,
      mutationOptions?: MutationOptions<McpLifecycleResponse>,
    ) => runMutation(() => startMcpServer(serverId), mutationOptions),
    [runMutation],
  );

  const stopServer = useCallback(
    (
      serverId: string,
      mutationOptions?: MutationOptions<McpLifecycleResponse>,
    ) => runMutation(() => stopMcpServer(serverId), mutationOptions),
    [runMutation],
  );

  const restartServer = useCallback(
    (
      serverId: string,
      mutationOptions?: MutationOptions<McpLifecycleResponse>,
    ) => runMutation(() => restartMcpServer(serverId), mutationOptions),
    [runMutation],
  );

  const checkServer = useCallback(
    (
      serverId: string,
      mutationOptions?: MutationOptions<McpLifecycleResponse>,
    ) => runMutation(() => checkMcpServer(serverId), mutationOptions),
    [runMutation],
  );

  return {
    checkServer,
    createServer,
    deleteServer,
    error,
    pending: pendingCount > 0,
    restartServer,
    startServer,
    stopServer,
    updateServer,
  };
}

function asError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error));
}
