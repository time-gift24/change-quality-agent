// @vitest-environment jsdom

import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
import { useMcpMutations, useMcpServerDetail, useMcpServers } from "./hooks";
import type { McpServerCreate, McpServerDetail, McpServerSummary } from "./types";

vi.mock("./api", () => ({
  checkMcpServer: vi.fn(),
  createMcpServer: vi.fn(),
  deleteMcpServer: vi.fn(),
  getMcpServer: vi.fn(),
  listMcpServers: vi.fn(),
  restartMcpServer: vi.fn(),
  startMcpServer: vi.fn(),
  stopMcpServer: vi.fn(),
  updateMcpServer: vi.fn(),
}));

describe("mcp hooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads server list on initial render", async () => {
    vi.mocked(listMcpServers).mockResolvedValueOnce([
      buildSummary({ id: "srv-1", name: "Server 1" }),
    ]);

    const { result } = renderHook(() => useMcpServers());

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBeNull();
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data[0]?.id).toBe("srv-1");
    expect(listMcpServers).toHaveBeenCalledTimes(1);
  });

  it("refreshes list after mutation success", async () => {
    vi.mocked(listMcpServers)
      .mockResolvedValueOnce([buildSummary({ id: "srv-1", name: "Server 1" })])
      .mockResolvedValueOnce([
        buildSummary({ id: "srv-1", name: "Server 1" }),
        buildSummary({ id: "srv-2", name: "Server 2" }),
      ]);

    vi.mocked(createMcpServer).mockResolvedValueOnce(
      buildDetail({ id: "srv-2", name: "Server 2" }),
    );

    const { result } = renderHook(() => {
      const servers = useMcpServers();
      const mutations = useMcpMutations({
        onSuccess: async () => {
          await servers.refetch();
        },
      });

      return { mutations, servers };
    });

    await waitFor(() => {
      expect(result.current.servers.data).toHaveLength(1);
    });

    await act(async () => {
      await result.current.mutations.createServer({
        command: "echo",
        name: "Server 2",
        transport: "stdio",
      } satisfies McpServerCreate);
    });

    await waitFor(() => {
      expect(result.current.servers.data).toHaveLength(2);
    });

    expect(result.current.mutations.pending).toBe(false);
    expect(result.current.mutations.error).toBeNull();
    expect(createMcpServer).toHaveBeenCalledTimes(1);
    expect(listMcpServers).toHaveBeenCalledTimes(2);
  });

  it("refreshes selected detail after mutation success", async () => {
    vi.mocked(getMcpServer)
      .mockResolvedValueOnce(
        buildDetail({ id: "srv-1", name: "Server 1", tool_count: 0 }),
      )
      .mockResolvedValueOnce(
        buildDetail({ id: "srv-1", name: "Server 1", tool_count: 2 }),
      );

    vi.mocked(updateMcpServer).mockResolvedValueOnce(
      buildDetail({ id: "srv-1", name: "Server 1", tool_count: 2 }),
    );

    const { result } = renderHook(() => {
      const detail = useMcpServerDetail("srv-1");
      const mutations = useMcpMutations({
        onSuccess: async () => {
          await detail.refetch();
        },
      });

      return { detail, mutations };
    });

    await waitFor(() => {
      expect(result.current.detail.data?.tool_count).toBe(0);
    });

    await act(async () => {
      await result.current.mutations.updateServer("srv-1", {
        name: "Server 1 Updated",
      });
    });

    await waitFor(() => {
      expect(result.current.detail.data?.tool_count).toBe(2);
    });

    expect(result.current.mutations.pending).toBe(false);
    expect(result.current.mutations.error).toBeNull();
    expect(updateMcpServer).toHaveBeenCalledTimes(1);
    expect(getMcpServer).toHaveBeenCalledTimes(2);
  });
});

function buildSummary(overrides: Partial<McpServerSummary> = {}): McpServerSummary {
  return {
    args: [],
    command: "echo",
    desired_state: "running",
    enabled: true,
    env: {},
    headers: {},
    id: "srv-default",
    last_checked_at: null,
    last_error: null,
    name: "Default Server",
    runtime_status: "running",
    tool_count: 0,
    transport: "stdio",
    url: null,
    ...overrides,
  };
}

function buildDetail(overrides: Partial<McpServerDetail> = {}): McpServerDetail {
  return {
    ...buildSummary(overrides),
    tools: [],
    ...overrides,
  };
}
