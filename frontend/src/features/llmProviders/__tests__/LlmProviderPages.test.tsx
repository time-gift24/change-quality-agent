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
const testProviderModel = vi.fn();

beforeEach(() => {
  refetchProviders.mockReset();
  refetchDetail.mockReset();
  createProvider.mockReset();
  updateProvider.mockReset();
  deleteProvider.mockReset();
  testProviderModel.mockReset();

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
    testProviderModel,
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
    expect(screen.getByRole("alertdialog")).toHaveTextContent("确认删除 Provider");
    fireEvent.click(screen.getByRole("button", { name: "确认删除" }));

    await waitFor(() => expect(deleteProvider).toHaveBeenCalledWith("provider-1"));
    expect(screen.getByText("Provider 列表")).toBeInTheDocument();
  });

  it("tests a configured model from detail page", async () => {
    testProviderModel.mockResolvedValue({
      error: null,
      latency_ms: 20,
      message: "连通性测试通过。",
      request: {
        messages: [{ content: "请简短回复：连通性测试通过。", role: "user" }],
        model: "gpt-5-mini",
        provider_type: "openai",
      },
      response: {
        content: "**连通性测试通过。**",
        raw: { content: "**连通性测试通过。**", type: "ai" },
      },
      status: "ok",
    });

    render(
      <MemoryRouter initialEntries={["/llm-providers/provider-1"]}>
        <Routes>
          <Route element={<LlmProviderDetailPage />} path="/llm-providers/:providerId" />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "测试 gpt-5-mini" }));

    await waitFor(() => expect(testProviderModel).toHaveBeenCalledWith("provider-1", "gpt-5-mini"));
    expect(await screen.findByRole("status")).toHaveTextContent("20ms");
    expect(screen.getByTestId("stream-markdown")).toHaveTextContent("连通性测试通过。");
    expect(screen.getByText(/provider_type/)).toBeInTheDocument();
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
    expect(screen.getByRole("combobox", { name: /Provider Type/ })).toHaveValue("openai");
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
    models: ["gpt-5-mini"],
    provider_type: "openai",
    updated_at: "2026-05-27T00:00:00Z",
  };
}
