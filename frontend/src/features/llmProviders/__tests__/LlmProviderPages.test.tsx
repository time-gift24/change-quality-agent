// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { useLlmProviderDetail, useLlmProviderMutations, useLlmProviders } from "../hooks";
import { LlmProviderDetailPage } from "../pages/LlmProviderDetailPage";
import { LlmProviderCreatePage, LlmProviderEditPage } from "../pages/LlmProviderFormPage";
import { LlmProviderListPage } from "../pages/LlmProviderListPage";
import type { LlmProviderDetail } from "../types";

vi.mock("../hooks", () => ({
  useLlmProviderDetail: vi.fn(),
  useLlmProviderMutations: vi.fn(),
  useLlmProviders: vi.fn(),
}));

const provider = buildProvider();
const refetchProviders = vi.fn();
const refetchDetail = vi.fn();
const createProvider = vi.fn();
const updateProvider = vi.fn();
const deleteProvider = vi.fn();

beforeEach(() => {
  refetchProviders.mockReset();
  refetchDetail.mockReset();
  createProvider.mockReset();
  updateProvider.mockReset();
  deleteProvider.mockReset();

  vi.mocked(useLlmProviders).mockReturnValue({
    data: [provider],
    error: null,
    loading: false,
    refetch: refetchProviders,
  });
  vi.mocked(useLlmProviderDetail).mockReturnValue({
    data: provider,
    error: null,
    loading: false,
    refetch: refetchDetail,
  });
  vi.mocked(useLlmProviderMutations).mockReturnValue({
    createProvider,
    deleteProvider,
    error: null,
    pending: false,
    updateProvider,
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("LLM provider pages", () => {
  it("renders list rows and navigates to create", () => {
    render(
      <MemoryRouter initialEntries={["/llm-providers"]}>
        <Routes>
          <Route element={<LlmProviderListPage />} path="/llm-providers" />
          <Route element={<div>新增 Provider 页面</div>} path="/llm-providers/new" />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole("main", { name: "LLM Provider 管理主内容" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /OpenAI Main/ })).toHaveAttribute("href", "/llm-providers/provider-1");
    expect(screen.getByText("openai")).toBeInTheDocument();
    expect(screen.getByText("已配置")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "新增 Provider" }));

    expect(screen.getByText("新增 Provider 页面")).toBeInTheDocument();
  });

  it("renders detail with masked config and deletes after confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    deleteProvider.mockResolvedValue(undefined);

    render(
      <MemoryRouter initialEntries={["/llm-providers/provider-1"]}>
        <Routes>
          <Route element={<LlmProviderDetailPage />} path="/llm-providers/:providerId" />
          <Route element={<div>Provider 列表</div>} path="/llm-providers" />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Authorization")).toBeInTheDocument();
    expect(screen.getAllByText("********").length).toBeGreaterThan(0);
    expect(screen.queryByText("sk-test")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "删除" }));

    await waitFor(() => expect(deleteProvider).toHaveBeenCalledWith("provider-1"));
    expect(screen.getByText("Provider 列表")).toBeInTheDocument();
  });

  it("creates provider and navigates to detail", async () => {
    createProvider.mockResolvedValue(provider);

    render(
      <MemoryRouter initialEntries={["/llm-providers/new"]}>
        <Routes>
          <Route element={<LlmProviderCreatePage />} path="/llm-providers/new" />
          <Route element={<div>Provider 详情</div>} path="/llm-providers/:providerId" />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText(/Display Name/), {
      target: { value: "OpenAI Main" },
    });
    fireEvent.change(screen.getByLabelText(/Provider Type/), {
      target: { value: "openai" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存 Provider" }));

    await waitFor(() => expect(createProvider).toHaveBeenCalled());
    expect(screen.getByText("Provider 详情")).toBeInTheDocument();
  });

  it("renders edit page for existing provider", () => {
    render(
      <MemoryRouter initialEntries={["/llm-providers/provider-1/edit"]}>
        <Routes>
          <Route element={<LlmProviderEditPage />} path="/llm-providers/:providerId/edit" />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByDisplayValue("OpenAI Main")).toBeInTheDocument();
    expect(screen.getByText(/留空表示保留现有 API Key/)).toBeInTheDocument();
  });
});

function buildProvider(): LlmProviderDetail {
  return {
    api_key_configured: true,
    base_url: "https://api.openai.com/v1",
    created_at: "2026-05-27T00:00:00Z",
    default_headers: { Authorization: "********", "X-Tenant": "quality" },
    default_query: { token: "********" },
    description: "Primary provider",
    display_name: "OpenAI Main",
    enabled: true,
    id: "provider-1",
    provider_type: "openai",
    updated_at: "2026-05-27T00:00:00Z",
  };
}
