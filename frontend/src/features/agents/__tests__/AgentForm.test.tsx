// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AgentForm, buildAgentDraftPayload } from "../components/AgentForm";
import type { AgentDetail } from "../types";
import type { LlmProviderSummary } from "../../llmProviders/types";

afterEach(() => {
  cleanup();
});

describe("AgentForm", () => {
  it("trims draft model and provider identifiers when building payload", () => {
    expect(
      buildAgentDraftPayload({
        codeAgentModel: " codeagent:deepseek-v4-pro ",
        modelSource: "codeagent",
        selectedProviderId: " ignored-provider ",
        selectedProviderModel: " ignored-model ",
        systemPrompt: " 提示词 ",
      }),
    ).toEqual({
      mcp_server_ids: [],
      model: "codeagent:deepseek-v4-pro",
      model_config: {},
      provider_id: null,
      system_prompt: "提示词",
      tool_allowlist: [],
    });

    expect(
      buildAgentDraftPayload({
        codeAgentModel: " ignored-codeagent ",
        modelSource: "provider",
        selectedProviderId: " provider-2 ",
        selectedProviderModel: " claude-sonnet-5 ",
        systemPrompt: " Provider 提示词 ",
      }),
    ).toEqual({
      mcp_server_ids: [],
      model: "claude-sonnet-5",
      model_config: {},
      provider_id: "provider-2",
      system_prompt: "Provider 提示词",
      tool_allowlist: [],
    });
  });

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
    fireEvent.change(screen.getByLabelText("系统提示词"), {
      target: { value: " 你是谨慎的评审助手。 " },
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
        system_prompt: "你是谨慎的评审助手。",
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
    fireEvent.change(screen.getByLabelText("系统提示词"), {
      target: { value: "使用已配置的 Provider。" },
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
        system_prompt: "使用已配置的 Provider。",
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
    fireEvent.click(screen.getByRole("button", { name: "切换到编辑模式" }));
    expect(screen.getByLabelText("系统提示词")).toHaveValue("已有系统提示词。");
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
        system_prompt: "已有系统提示词。",
        tool_allowlist: [],
      },
      enabled: false,
    });
  });

  it("blocks edit save when draft provider is unavailable", () => {
    const onUpdate = vi.fn().mockResolvedValue(undefined);
    const agent = buildAgent({
      draft: {
        mcp_server_ids: [],
        model: "disabled-model",
        model_config: {},
        provider_id: "provider-disabled",
        system_prompt: "已有系统提示词。",
        tool_allowlist: [],
      },
    });
    render(
      <AgentForm
        agent={agent}
        mode="edit"
        onUpdate={onUpdate}
        providers={[
          buildProvider({
            display_name: "OpenAI Main",
            id: "provider-1",
            models: ["gpt-5-mini"],
          }),
        ]}
        providersLoading={false}
      />,
    );

    expect(screen.getByLabelText("LLM Provider")).toHaveValue("provider-disabled");
    expect(screen.getByRole("option", { name: "provider-disabled (不可用)" })).toBeInTheDocument();
    expect(screen.getByText("当前 draft 引用的 Provider 不可用，请选择一个已启用的 LLM Provider。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存 Agent" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "保存 Agent" }));

    expect(onUpdate).not.toHaveBeenCalled();
  });

  it("blocks edit save when provider draft model is unavailable", () => {
    const onUpdate = vi.fn().mockResolvedValue(undefined);
    const agent = buildAgent({
      draft: {
        mcp_server_ids: [],
        model: "gpt-legacy",
        model_config: {},
        provider_id: "provider-1",
        system_prompt: "已有系统提示词。",
        tool_allowlist: [],
      },
    });
    render(
      <AgentForm
        agent={agent}
        mode="edit"
        onUpdate={onUpdate}
        providers={[
          buildProvider({
            display_name: "OpenAI Main",
            id: "provider-1",
            models: ["gpt-5-mini", "gpt-5"],
          }),
        ]}
        providersLoading={false}
      />,
    );

    expect(screen.getByLabelText("Provider 模型")).toHaveValue("gpt-legacy");
    expect(screen.getByRole("option", { name: "gpt-legacy (不可用)" })).toBeInTheDocument();
    expect(screen.getByText("当前 draft 引用的模型不在所选 Provider 的模型列表中，请重新选择模型。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存 Agent" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "保存 Agent" }));

    expect(onUpdate).not.toHaveBeenCalled();
  });

  it("blocks edit save when CodeAgent draft model is unavailable", () => {
    const onUpdate = vi.fn().mockResolvedValue(undefined);
    const agent = buildAgent({
      draft: {
        mcp_server_ids: [],
        model: "codeagent:legacy",
        model_config: {},
        provider_id: null,
        system_prompt: "已有系统提示词。",
        tool_allowlist: [],
      },
    });
    render(
      <AgentForm
        agent={agent}
        mode="edit"
        onUpdate={onUpdate}
        providers={buildProviders()}
        providersLoading={false}
      />,
    );

    expect(screen.getByLabelText("CodeAgent 模型")).toHaveValue("codeagent:legacy");
    expect(screen.getByRole("option", { name: "codeagent:legacy (不可用)" })).toBeInTheDocument();
    expect(screen.getByText("当前 draft 引用的 CodeAgent 模型不在可选列表中，请重新选择模型。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存 Agent" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "保存 Agent" }));

    expect(onUpdate).not.toHaveBeenCalled();
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

function buildAgent(overrides: Partial<AgentDetail> = {}): AgentDetail {
  return {
    created_at: "2026-05-28T00:00:00Z",
    description: "Existing description",
    display_name: "Existing Agent",
    draft: {
      mcp_server_ids: [],
      model: "gpt-5-mini",
      model_config: {},
      provider_id: "provider-1",
      system_prompt: "已有系统提示词。",
      tool_allowlist: [],
    },
    enabled: false,
    has_draft: true,
    id: "agent-1",
    latest_version: null,
    updated_at: "2026-05-28T00:00:00Z",
    ...overrides,
  };
}
