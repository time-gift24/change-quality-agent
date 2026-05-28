// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/apiClient";
import {
  createLlmProvider,
  deleteLlmProvider,
  getLlmProvider,
  listLlmProviders,
  updateLlmProvider,
} from "./api";
import type { LlmProviderCreate, LlmProviderDetail } from "./types";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("LLM provider API", () => {
  it("calls list endpoint with GET", async () => {
    const providers: LlmProviderDetail[] = [];
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(providers));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listLlmProviders()).resolves.toEqual(providers);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/llm-providers",
      expect.objectContaining({ headers: expect.any(Headers) }),
    );
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBeUndefined();
  });

  it("calls create endpoint with POST", async () => {
    const payload: LlmProviderCreate = {
      api_key: "sk-test",
      base_url: "https://api.openai.com/v1",
      default_headers: { "X-Tenant": "quality" },
      default_query: { "api-version": "2026-01-01" },
      display_name: "OpenAI Main",
      enabled: true,
      provider_type: "openai",
    };
    const detail = buildProvider();
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(detail, 201, "Created"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(createLlmProvider(payload)).resolves.toEqual(detail);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/llm-providers",
      expect.objectContaining({
        body: JSON.stringify(payload),
        method: "POST",
      }),
    );
  });

  it("calls get and patch endpoints with encoded provider id", async () => {
    const detail = buildProvider();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(detail))
      .mockResolvedValueOnce(jsonResponse(detail));
    vi.stubGlobal("fetch", fetchMock);

    await getLlmProvider("provider-1");
    await updateLlmProvider("provider-1", { display_name: "OpenAI Renamed" });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/llm-providers/provider-1",
      expect.objectContaining({ headers: expect.any(Headers) }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/llm-providers/provider-1",
      expect.objectContaining({
        body: JSON.stringify({ display_name: "OpenAI Renamed" }),
        method: "PATCH",
      }),
    );
  });

  it("calls delete endpoint with DELETE and accepts 204", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(deleteLlmProvider("provider-1")).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/llm-providers/provider-1",
      expect.objectContaining({
        headers: expect.any(Headers),
        method: "DELETE",
      }),
    );
  });

  it("throws ApiError detail when delete fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(errorResponse(404, "Not Found", "LLM provider not found.")),
    );

    await expect(deleteLlmProvider("missing")).rejects.toMatchObject({
      detail: "LLM provider not found.",
      status: 404,
      statusText: "Not Found",
    } satisfies Partial<ApiError>);
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

function jsonResponse(body: unknown, status = 200, statusText = "OK") {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
    statusText,
  });
}

function errorResponse(status: number, statusText: string, detail: string) {
  return jsonResponse({ detail }, status, statusText);
}
