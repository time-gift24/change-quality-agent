import { useCallback, useEffect, useRef, useState } from "react";

import {
  createAgent as createAgentApi,
  getAgent,
  listAgents,
  updateAgentDraft as updateAgentDraftApi,
} from "./api";
import type {
  AgentCreate,
  AgentDetail,
  AgentDraftUpdate,
  AgentSummary,
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

export function useAgents(): AsyncStateWithRefetch<AgentSummary[]> {
  const [state, setState] = useState<AsyncState<AgentSummary[]>>({
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
      const agents = await listAgents();
      if (!mountedRef.current || requestIdRef.current !== requestId) return;
      setState({ data: agents, error: null, loading: false });
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

export function useAgentDetail(
  agentId: string | null | undefined,
): AsyncStateWithRefetch<AgentDetail | null> {
  const [state, setState] = useState<AsyncState<AgentDetail | null>>({
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

    if (!agentId) {
      setState({ data: null, error: null, loading: false });
      return;
    }

    setState({ data: null, error: null, loading: true });

    try {
      const agent = await getAgent(agentId);
      if (!mountedRef.current || requestIdRef.current !== requestId) return;
      setState({ data: agent, error: null, loading: false });
    } catch (error) {
      if (!mountedRef.current || requestIdRef.current !== requestId) return;
      setState({ data: null, error: asError(error), loading: false });
    }
  }, [agentId]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  return { ...state, refetch };
}

export function useAgentMutations() {
  const [pendingCount, setPendingCount] = useState(0);
  const [error, setError] = useState<Error | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const runMutation = useCallback(
    async <TResult,>(
      action: () => Promise<TResult>,
      options?: MutationOptions<TResult>,
    ): Promise<TResult> => {
      if (mountedRef.current) {
        setPendingCount((current) => current + 1);
        setError(null);
      }
      try {
        const result = await action();
        await options?.onSuccess?.(result);
        return result;
      } catch (mutationError) {
        const nextError = asError(mutationError);
        if (mountedRef.current) {
          setError(nextError);
        }
        throw nextError;
      } finally {
        if (mountedRef.current) {
          setPendingCount((current) => Math.max(0, current - 1));
        }
      }
    },
    [],
  );

  return {
    createAgent: (
      payload: AgentCreate,
      options?: MutationOptions<AgentDetail>,
    ) => runMutation(() => createAgentApi(payload), options),
    error,
    pending: pendingCount > 0,
    updateAgentDraft: (
      agentId: string,
      payload: AgentDraftUpdate,
      options?: MutationOptions<AgentDetail>,
    ) => runMutation(() => updateAgentDraftApi(agentId, payload), options),
  };
}

function asError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error));
}
