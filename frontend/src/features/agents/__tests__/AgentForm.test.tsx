// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AgentForm } from "../components/AgentForm";
import type { AgentDetail } from "../types";
import type { LlmProviderSummary } from "../../llmProviders/types";

afterEach(() => {
  cleanup();
});

describe("AgentForm", () => {
  it("creates a CodeAgent-backed draft from hard-coded model dropdown", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    render(
      <AgentForm
        agent={null}
        mode="create"
        onCreate={onCreate}
        providers={buildProviders()}
        providersLoading={false}
      />,
    );

    fireEvent.change(screen.getByLabelText("Agent 名称"), {
      target: { value: " Release Reviewer " },
    });
    fireEvent.change(screen.getByLabelText("System Prompt"), {
      target: { value: " You are careful. " },
    });
    fireEvent.change(screen.getByLabelText("CodeAgent 模型"), {
      target: { value: "codeagent:codeagent-v4-pro" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存 Agent" }));

    await waitFor(() => expect(onCreate).toHaveBeenCalledTimes(1));
    expect(onCreate).toHaveBeenCalledWith({
      description: null,
      display_name: "Release Reviewer",
      draft: {
        mcp_server_ids: [],
        model: "codeagent:codeagent-v4-pro",
        model_config: {},
        provider_id: null,
        system_prompt: "You are careful.",
        tool_allowlist: [],
      },
    });
  });

  it("creates a provider-backed draft from provider and provider model dropdowns", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    render(
      <AgentForm
        agent={null}
        mode="create"
        onCreate={onCreate}
        providers={buildProviders()}
        providersLoading={false}
      />,
    );

    fireEvent.change(screen.getByLabelText("Agent 名称"), {
      target: { value: "Provider Agent" },
    });
    fireEvent.change(screen.getByLabelText("System Prompt"), {
      target: { value: "Use the configured provider." },
    });
    fireEvent.change(screen.getByLabelText("模型来源"), {
      target: { value: "provider" },
    });
    fireEvent.change(screen.getByLabelText("LLM Provider"), {
      target: { value: "provider-2" },
    });
    fireEvent.change(screen.getByLabelText("Provider 模型"), {
      target: { value: "claude-sonnet-5" },
    });
    expect(screen.queryByRole("option", { name: "Disabled Provider" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "保存 Agent" }));

    await waitFor(() => expect(onCreate).toHaveBeenCalledTimes(1));
    expect(onCreate).toHaveBeenCalledWith({
      description: null,
      display_name: "Provider Agent",
      draft: {
        mcp_server_ids: [],
        model: "claude-sonnet-5",
        model_config: {},
        provider_id: "provider-2",
        system_prompt: "Use the configured provider.",
        tool_allowlist: [],
      },
    });
  });

  it("disables save when selected provider has no models and shows guidance", () => {
    render(
      <AgentForm
        agent={null}
        mode="create"
        onCreate={vi.fn()}
        providers={[buildProvider({ id: "empty-provider", models: [] })]}
        providersLoading={false}
      />,
    );

    fireEvent.change(screen.getByLabelText("模型来源"), {
      target: { value: "provider" },
    });

    expect(screen.getByText("先到 LLM Provider 页面补模型列表")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存 Agent" })).toBeDisabled();
  });

  it("initializes edit form from existing draft", async () => {
    const onUpdate = vi.fn().mockResolvedValue(undefined);
    const agent = buildAgent();
    render(
      <AgentForm
        agent={agent}
        mode="edit"
        onUpdate={onUpdate}
        providers={buildProviders()}
        providersLoading={false}
      />,
    );

    expect(screen.getByLabelText("Agent 名称")).toHaveValue("Existing Agent");
    expect(screen.getByLabelText("System Prompt")).toHaveValue("Existing prompt.");
    expect(screen.getByLabelText("模型来源")).toHaveValue("provider");
    expect(screen.getByLabelText("LLM Provider")).toHaveValue("provider-1");
    expect(screen.getByLabelText("Provider 模型")).toHaveValue("gpt-5-mini");
    expect(screen.getByLabelText("启用 Agent")).not.toBeChecked();

    fireEvent.click(screen.getByRole("button", { name: "保存 Agent" }));

    await waitFor(() => expect(onUpdate).toHaveBeenCalledTimes(1));
    expect(onUpdate).toHaveBeenCalledWith("agent-1", {
      description: "Existing description",
      display_name: "Existing Agent",
      draft: {
        mcp_server_ids: [],
        model: "gpt-5-mini",
        model_config: {},
        provider_id: "provider-1",
        system_prompt: "Existing prompt.",
        tool_allowlist: [],
      },
      enabled: false,
    });
  });
});

function buildProviders(): LlmProviderSummary[] {
  return [
    buildProvider({
      display_name: "OpenAI Main",
      id: "provider-1",
      models: ["gpt-5-mini", "gpt-5"],
      provider_type: "openai",
    }),
    buildProvider({
      display_name: "Anthropic Main",
      id: "provider-2",
      models: ["claude-haiku-5", "claude-sonnet-5"],
      provider_type: "anthropic",
    }),
    buildProvider({
      display_name: "Disabled Provider",
      enabled: false,
      id: "provider-disabled",
      models: ["disabled-model"],
    }),
  ];
}

function buildProvider(overrides: Partial<LlmProviderSummary> = {}): LlmProviderSummary {
  return {
    api_key_configured: true,
    base_url: "https://api.example.test/v1",
    created_at: "2026-05-28T00:00:00Z",
    default_headers: {},
    default_query: {},
    description: null,
    display_name: "Provider",
    enabled: true,
    id: "provider-1",
    models: ["gpt-5-mini"],
    provider_type: "openai",
    updated_at: "2026-05-28T00:00:00Z",
    ...overrides,
  };
}

function buildAgent(): AgentDetail {
  return {
    created_at: "2026-05-28T00:00:00Z",
    description: "Existing description",
    display_name: "Existing Agent",
    draft: {
      mcp_server_ids: [],
      model: "gpt-5-mini",
      model_config: {},
      provider_id: "provider-1",
      system_prompt: "Existing prompt.",
      tool_allowlist: [],
    },
    enabled: false,
    has_draft: true,
    id: "agent-1",
    latest_version: null,
    updated_at: "2026-05-28T00:00:00Z",
  };
}
