// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LlmProviderForm } from "../components/LlmProviderForm";
import type { LlmProviderDetail } from "../types";

afterEach(() => {
  cleanup();
});

describe("LlmProviderForm", () => {
  it("creates a provider with parsed headers and query values", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    render(<LlmProviderForm mode="create" onCreate={onCreate} provider={null} />);

    fireEvent.change(screen.getByLabelText(/Provider Key/), {
      target: { value: "openai_main" },
    });
    fireEvent.change(screen.getByLabelText(/Display Name/), {
      target: { value: "OpenAI Main" },
    });
    fireEvent.change(screen.getByLabelText(/Provider Type/), {
      target: { value: "openai" },
    });
    fireEvent.change(screen.getByLabelText(/Base URL/), {
      target: { value: "https://api.openai.com/v1" },
    });
    fireEvent.change(screen.getByLabelText(/API Key/), {
      target: { value: "sk-test" },
    });
    fireEvent.change(screen.getByLabelText(/Default Headers/), {
      target: { value: "X-Tenant=quality" },
    });
    fireEvent.change(screen.getByLabelText(/Default Query/), {
      target: { value: "api-version=2026-01-01" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存 Provider" }));

    await waitFor(() => expect(onCreate).toHaveBeenCalledTimes(1));
    expect(onCreate).toHaveBeenCalledWith({
      api_key: "sk-test",
      base_url: "https://api.openai.com/v1",
      default_headers: { "X-Tenant": "quality" },
      default_query: { "api-version": "2026-01-01" },
      description: null,
      display_name: "OpenAI Main",
      enabled: true,
      key: "openai_main",
      provider_type: "openai",
    });
  });

  it("omits api_key on edit unless replacement or clear is requested", async () => {
    const onUpdate = vi.fn().mockResolvedValue(undefined);
    render(
      <LlmProviderForm
        mode="edit"
        onUpdate={onUpdate}
        provider={buildProvider()}
      />,
    );

    fireEvent.change(screen.getByLabelText(/Display Name/), {
      target: { value: "OpenAI Renamed" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存 Provider" }));

    await waitFor(() => expect(onUpdate).toHaveBeenCalledTimes(1));
    expect(onUpdate).toHaveBeenCalledWith("openai_main", expect.not.objectContaining({ api_key: expect.anything() }));
    expect(onUpdate).toHaveBeenCalledWith(
      "openai_main",
      expect.not.objectContaining({ default_headers: expect.anything() }),
    );

    onUpdate.mockClear();
    fireEvent.click(screen.getByLabelText("清除现有 API Key"));
    fireEvent.click(screen.getByRole("button", { name: "保存 Provider" }));

    await waitFor(() => expect(onUpdate).toHaveBeenCalledTimes(1));
    expect(onUpdate).toHaveBeenCalledWith("openai_main", expect.objectContaining({ api_key: null }));
  });

  it("rejects changed redacted header placeholders on edit", async () => {
    const onUpdate = vi.fn().mockResolvedValue(undefined);
    render(
      <LlmProviderForm
        mode="edit"
        onUpdate={onUpdate}
        provider={buildProvider()}
      />,
    );

    fireEvent.change(screen.getByLabelText(/Default Headers/), {
      target: { value: "Authorization=********\nX-Tenant=renamed" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存 Provider" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("脱敏值 ********");
    expect(onUpdate).not.toHaveBeenCalled();
  });

  it("rejects malformed KEY=VALUE lines", async () => {
    const onCreate = vi.fn();
    render(<LlmProviderForm mode="create" onCreate={onCreate} provider={null} />);

    fireEvent.change(screen.getByLabelText(/Provider Key/), {
      target: { value: "openai_main" },
    });
    fireEvent.change(screen.getByLabelText(/Display Name/), {
      target: { value: "OpenAI Main" },
    });
    fireEvent.change(screen.getByLabelText(/Provider Type/), {
      target: { value: "openai" },
    });
    fireEvent.change(screen.getByLabelText(/Default Headers/), {
      target: { value: "broken-line" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存 Provider" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Default Headers");
    expect(onCreate).not.toHaveBeenCalled();
  });
});

function buildProvider(): LlmProviderDetail {
  return {
    api_key_configured: true,
    base_url: "https://api.openai.com/v1",
    created_at: "2026-05-27T00:00:00Z",
    default_headers: { Authorization: "********", "X-Tenant": "quality" },
    default_query: {},
    description: "Primary",
    display_name: "OpenAI Main",
    enabled: true,
    id: "provider-1",
    key: "openai_main",
    provider_type: "openai",
    updated_at: "2026-05-27T00:00:00Z",
  };
}
