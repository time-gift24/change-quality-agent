# LLM Provider 与模型运行能力

本文档说明当前项目的 LLM Provider 管理、CodeAgent 内网模型接入、Agent runtime 模型解析，以及前后端代码分布。它取代 `docs/plans/` 下的临时设计和实施计划。

## 当前能力

### 两类模型来源

系统当前支持两类 chat model 创建路径：

- `codeagent:<model-name>`：内部 CodeAgent 模型。运行时使用 `langchain_deepseek.ChatDeepSeek`，协议按 DeepSeek chat 兼容接口处理。
- 存储型 LLM Provider：普通 LangChain provider。Agent version 保存 `provider_id` 和裸模型名，由后端读取数据库中的 provider 配置后调用 `langchain.chat_models.init_chat_model`。

这两条路径互斥：

- 使用 `codeagent:` 时，Agent version 不应设置 `provider_id`。
- 使用 `provider_id` 时，`model` 必须是裸模型名，例如 `gpt-5-mini`，不能带 `openai:` 或 `codeagent:` 前缀。

### CodeAgent 内网模型

CodeAgent 是项目内置的特殊模型工厂路径，入口约定为：

```json
{
  "model": "codeagent:deepseek-v4-pro",
  "model_config": {
    "temperature": 0,
    "reasoning_effort": "high",
    "model_kwargs": {
      "stream_options": {"include_usage": true}
    }
  }
}
```

运行时行为：

- 去掉 `codeagent:` 前缀后，把剩余部分作为 DeepSeek 模型名传给 `ChatDeepSeek`。
- `CODEAGENT_BASE_URL` 作为内网模型服务地址。
- `CODEAGENT_TOKEN_PROVIDER=codeagent` 选择内部 token provider。
- token header 不从 Agent API、Agent draft、Agent version 或 LLM Provider 表传入。
- HTTP client request hook 会在每次请求前调用 token provider 获取最新 header，避免长任务中复用过期 token。

CodeAgent 的 `model_config` 只允许承载模型参数，不允许塞入 provider 级配置。以下字段会被拒绝：

- `api_key`
- `api_base`
- `base_url`
- `default_headers`
- `http_client`
- `http_async_client`

### 普通 LLM Provider

普通 provider 通过 `/api/v1/llm-providers` 管理。它面向 LangChain `init_chat_model` 支持的 provider 类型，并把连接配置保存在数据库里。

核心字段：

- `display_name`: 用户可读名称。
- `description`: 可选说明。
- `provider_type`: LangChain `init_chat_model` 的 provider 类型，例如 `openai`、`deepseek`、`anthropic`、`azure_openai`。
- `base_url`: OpenAI-compatible 或其他 provider 的可选服务地址。
- `api_key`: 写入型密钥。API 响应不会返回明文。
- `default_headers`: 默认请求 header。响应中 secret-like key 会脱敏。
- `default_query`: 默认 query 参数。响应中 secret-like key 会脱敏。
- `models`: 该 provider 可用的模型名列表。
- `enabled`: 是否启用。

API 能力：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/v1/llm-providers` | 创建 provider。 |
| `GET` | `/api/v1/llm-providers` | 列出未删除 provider。 |
| `GET` | `/api/v1/llm-providers/{provider_id}` | 查看 provider 详情。 |
| `PATCH` | `/api/v1/llm-providers/{provider_id}` | 更新 provider 配置。 |
| `DELETE` | `/api/v1/llm-providers/{provider_id}` | 软删除 provider。 |
| `POST` | `/api/v1/llm-providers/{provider_id}/test` | 对 provider 下的某个模型做连通性测试。 |

`api_key` 更新语义：

- 创建时可以传入明文 `api_key`。
- 更新时省略 `api_key` 表示保留原值。
- 更新时显式传 `null` 表示清空。
- 响应只返回 `api_key_configured`，不返回明文。

### Provider 模型列表与连通性测试

一个 provider 可以配置多个模型名。详情页会按 `models` 列表逐个展示，并允许对单个模型发起连通性测试。

测试请求：

```json
{
  "model": "gpt-5-mini"
}
```

后端测试逻辑：

1. 校验 provider 存在。
2. 校验请求的 model 必须在 provider 的 `models` 列表中。
3. 用 provider 配置构造 `LlmProviderRuntimeConfig`。
4. 调用 `create_provider_chat_model(model, provider, temperature=0)`。
5. 发送固定测试消息 `[{ "role": "user", "content": "ping" }]`。
6. 返回成功或失败结果。

测试响应：

- `status`: `ok` 或 `failed`。
- `latency_ms`: 后端观测到的调用耗时。
- `message`: 成功时的模型文本输出。
- `error`: 失败时的脱敏错误。
- `request`: 后端构造的诊断 trace。
- `response`: LangChain 返回对象或异常转换后的诊断 trace。

注意：`request` 和 `response` 目前是调试 trace，不是严格强类型的后端结构体。外层 `LlmProviderModelTestResponse` 是 Pydantic schema，但 `request` / `response` 字段类型是 `dict[str, Any] | None`。其中 `request` 也不是底层 HTTP client 的原始 wire payload，而是后端根据 provider 配置、测试消息和测试参数重建出的诊断信息。

前端展示：

- 成功或失败状态、耗时、错误摘要。
- `模型响应` 区域复用质检运行的 `StreamMarkdown` 渲染模型内容。
- `完整交互信息` 折叠区展示 `Request` 和 `Response` JSON。

## Agent Runtime 接入

Agent draft 和 Agent version 都可以配置模型来源。

### CodeAgent Agent Version

适合内网 CodeAgent 模型：

```json
{
  "system_prompt": "You are a careful reviewer.",
  "model": "codeagent:deepseek-v4-pro",
  "provider_id": null,
  "model_config": {
    "temperature": 0,
    "reasoning_effort": "high",
    "model_kwargs": {
      "stream_options": {"include_usage": true}
    }
  }
}
```

### Stored Provider Agent Version

适合普通 provider：

```json
{
  "system_prompt": "You are a careful reviewer.",
  "model": "gpt-5-mini",
  "provider_id": "00000000-0000-0000-0000-000000000000",
  "model_config": {
    "temperature": 0
  }
}
```

运行时解析顺序：

1. `AgentRuntime` 读取已发布的 `agent_versions`。
2. 如果存在 `provider_id`，从数据库读取 provider，并调用 `create_provider_chat_model`。
3. 如果不存在 `provider_id`，调用默认 `create_chat_model`。
4. `create_chat_model` 对 `codeagent:` 走内部 CodeAgent 工厂；其他模型名 fallback 到 LangChain `init_chat_model`。
5. 最终 model 传给 `langchain.agents.create_agent`。

## 前后端代码分布

### 后端

LLM Provider API：

- `app/api/v1/llm_providers.py`: HTTP 路由、请求校验、错误映射、连通性测试入口。
- `app/schemas/llm_providers.py`: Pydantic 请求/响应 schema，包含 provider CRUD、模型测试响应、密钥脱敏。
- `app/models/llm_providers.py`: SQLAlchemy provider 表模型。
- `app/repositories/llm_providers.py`: provider 持久化、列表、更新、软删除。
- `app/api/deps.py`: provider repository 依赖注入。

模型创建与 token：

- `app/core/llm_models.py`: `create_chat_model`、`create_provider_chat_model`、CodeAgent factory、token-refreshing HTTP client。
- `app/core/llm_tokens.py`: token provider 抽象和 CodeAgent provider 实现。
- `app/core/llm_connectivity.py`: provider 单模型连通性测试、request/response trace、错误脱敏。
- `app/core/llm_provider_types.py`: 与 LangChain `init_chat_model` 对齐的 provider 类型枚举。
- `app/core/config.py`: `CODEAGENT_BASE_URL`、`CODEAGENT_TOKEN_PROVIDER` 等全局配置。

Agent runtime：

- `app/core/agent_runtime.py`: 解析 Agent version、provider_id、model_config，并创建 LangChain agent。
- `app/services/agents.py`: agent draft、publish、test run 服务层。
- `app/models/agents.py`: `agents`、`agent_versions`，包含 `provider_id` 和 `model_config` 持久化字段。
- `app/schemas/agents.py`: Agent draft/version API schema。

数据库迁移与契约：

- `migrations/versions/20260527_0006_add_llm_provider_and_agent_provider.py`: provider 表和 agent version provider 关联。
- `migrations/versions/20260527_0007_add_llm_provider_models.py`: provider `models` 字段。
- `api/openapi.yml`: 前后端共享 API 契约。

后端测试：

- `tests/test_llm_models.py`: 模型工厂、CodeAgent、provider fallback。
- `tests/test_llm_tokens.py`: token provider。
- `tests/test_llm_provider_schemas.py`: provider schema 和脱敏。
- `tests/test_llm_providers_api.py`: provider API 和模型测试接口。
- `tests/test_agent_runtime.py`: Agent runtime 模型创建路径。
- `tests/test_openapi_contract.py`: OpenAPI 契约。
- `tests/test_migrations.py`: migration 版本链。

### 前端

LLM Provider API 和状态：

- `frontend/src/features/llmProviders/api.ts`: provider CRUD、删除、模型连通性测试请求。
- `frontend/src/features/llmProviders/hooks.ts`: provider list/detail/mutation hooks。
- `frontend/src/features/llmProviders/types.ts`: provider 类型、provider type 候选、测试响应类型。

LLM Provider 页面：

- `frontend/src/features/llmProviders/pages/LlmProviderListPage.tsx`: provider 列表页。
- `frontend/src/features/llmProviders/pages/LlmProviderCreatePage.tsx`: 创建页。
- `frontend/src/features/llmProviders/pages/LlmProviderEditPage.tsx`: 编辑页。
- `frontend/src/features/llmProviders/pages/LlmProviderDetailPage.tsx`: 详情页、模型列表、单模型连通性测试、trace 展示。
- `frontend/src/features/llmProviders/pages/LlmProviderPageLayout.tsx`: provider 页面布局。

LLM Provider 组件：

- `frontend/src/features/llmProviders/components/LlmProviderForm.tsx`: 创建、编辑、查看表单；包含 provider type 下拉框、models 输入、dirty guard、字段错误展示。
- `frontend/src/features/llmProviders/components/LlmProviderTable.tsx`: provider 表格、搜索、刷新和移动端横向滚动提示。

复用的质检渲染模块：

- `frontend/src/features/runs/components/StreamMarkdown.tsx`: 被 provider 连通性测试复用，用于渲染模型响应 Markdown。

前端测试：

- `frontend/src/features/llmProviders/__tests__/LlmProviderForm.test.tsx`
- `frontend/src/features/llmProviders/__tests__/LlmProviderPages.test.tsx`
- `frontend/src/features/llmProviders/api.test.ts`

## 当前边界

- Provider 连通性测试目前只发送固定 `ping` 消息，不支持用户自定义测试 prompt。
- `request` / `response` trace 是自由 JSON，适合诊断展示；如果后续要长期稳定对外，应升级为强类型 Pydantic schema。
- Provider API key 仍是数据库明文字段；HTTP 响应会脱敏，但尚未实现存储层加密。
- CodeAgent token provider 已支持每次请求刷新 header，但真正 token 刷新策略取决于 provider 实现。
- 普通 provider 的 token/header 来自数据库配置，不走 CodeAgent token provider。
