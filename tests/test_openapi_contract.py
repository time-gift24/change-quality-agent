from pathlib import Path

import yaml


CONTRACT_PATH = Path(__file__).resolve().parents[1] / "api" / "openapi.yml"
HTTP_METHODS = {"delete", "get", "patch", "post", "put"}


def load_contract() -> dict:
    return yaml.safe_load(CONTRACT_PATH.read_text())


def iter_path_operations(paths: dict):
    for path, path_item in paths.items():
        for method, operation in path_item.items():
            if method in HTTP_METHODS:
                yield path, method, operation


def test_auth_paths_are_documented() -> None:
    contract = load_contract()
    paths = contract["paths"]

    assert contract["security"] == [{"CookieAuth": []}]
    assert "/api/auth/me" in paths
    assert "/api/auth/dev-login" in paths
    assert "/api/auth/logout" in paths
    assert {
        "name": "auth",
        "description": "Cookie-backed user authentication APIs for local development.",
    } in contract["tags"]
    assert contract["components"]["securitySchemes"]["CookieAuth"] == {
        "type": "apiKey",
        "in": "cookie",
        "name": "cqa_user",
    }
    assert "UserPublic" in contract["components"]["schemas"]
    assert "DevLoginRequest" in contract["components"]["schemas"]
    assert "401" in paths["/api/auth/me"]["get"]["responses"]
    assert paths["/api/auth/dev-login"]["post"]["security"] == []
    assert paths["/api/auth/logout"]["post"]["security"] == []


def test_protected_non_auth_operations_document_401() -> None:
    contract = load_contract()

    for path, method, operation in iter_path_operations(contract["paths"]):
        if path.startswith("/api/auth/"):
            continue

        assert "401" in operation["responses"], (
            f"{method.upper()} {path} is protected but does not document 401"
        )


def test_openapi_includes_mcp_server_routes() -> None:
    spec = load_contract()
    paths = spec["paths"]

    expected_paths = {
        "/api/mcp/servers": {"get", "post"},
        "/api/mcp/servers/{server_id}": {"get", "patch", "delete"},
        "/api/mcp/servers/{server_id}/start": {"post"},
        "/api/mcp/servers/{server_id}/stop": {"post"},
        "/api/mcp/servers/{server_id}/restart": {"post"},
        "/api/mcp/servers/{server_id}/check": {"post"},
    }

    for path, methods in expected_paths.items():
        assert path in paths
        assert methods <= set(paths[path])
        for method in methods:
            operation = paths[path][method]
            responses = operation["responses"]
            assert operation["security"] == [{"CookieAuth": []}]
            assert "401" in responses
            assert "403" in responses

    schemas = spec["components"]["schemas"]
    assert {
        "McpServerCreate",
        "McpServerUpdate",
        "McpServerSummary",
        "McpServerDetail",
        "McpLifecycleResponse",
    } <= set(schemas)
    assert set(spec["components"]["securitySchemes"]) == {"CookieAuth"}
    lifecycle_responses = paths["/api/mcp/servers/{server_id}/start"]["post"][
        "responses"
    ]
    assert "502" in lifecycle_responses


def test_agents_tag_and_paths_are_documented() -> None:
    contract = load_contract()

    tag_descriptions = {tag["name"]: tag["description"] for tag in contract["tags"]}
    assert tag_descriptions["agents"] == "Agent definitions and published versions."

    paths = contract["paths"]
    expected_operations = {
        ("/api/agents", "get"): {"200", "422"},
        ("/api/agents", "post"): {"201", "422"},
        ("/api/agents/{agent_id}", "get"): {"200", "404", "422"},
        ("/api/agents/{agent_id}", "delete"): {"204", "404", "422"},
        ("/api/agents/{agent_id}/draft", "patch"): {"200", "404", "422"},
        ("/api/agents/{agent_id}/publish", "post"): {
            "201",
            "400",
            "404",
            "422",
        },
        ("/api/agents/{agent_id}/versions", "get"): {"200", "404", "422"},
        ("/api/agents/{agent_id}/versions/{version_number}", "get"): {
            "200",
            "404",
            "422",
        },
    }

    for (path, method), statuses in expected_operations.items():
        operation = paths[path][method]
        assert operation["tags"] == ["agents"]
        assert statuses <= set(operation["responses"])


def test_llm_provider_tag_and_paths_are_documented() -> None:
    contract = load_contract()

    tag_descriptions = {tag["name"]: tag["description"] for tag in contract["tags"]}
    assert tag_descriptions["llm-providers"] == (
        "Stored LangChain chat model provider configuration."
    )

    paths = contract["paths"]
    expected_operations = {
        ("/api/v1/llm-providers", "get"): {"200"},
        ("/api/v1/llm-providers", "post"): {"201", "422"},
        ("/api/v1/llm-providers/{provider_id}", "get"): {"200", "404", "422"},
        ("/api/v1/llm-providers/{provider_id}", "patch"): {"200", "404", "422"},
        ("/api/v1/llm-providers/{provider_id}", "delete"): {"204", "404", "422"},
        ("/api/v1/llm-providers/{provider_id}/test", "post"): {"200", "400", "404", "502", "422"},
    }

    for (path, method), statuses in expected_operations.items():
        operation = paths[path][method]
        assert operation["tags"] == ["llm-providers"]
        assert statuses <= set(operation["responses"])


def test_openapi_does_not_document_generic_runs() -> None:
    paths = load_contract()["paths"]
    legacy_runs_prefix = "/api/" + "runs"
    legacy_agent_path = "/api/agents/{agent_key}/" + "test-" + "runs"

    assert not any(path.startswith(legacy_runs_prefix) for path in paths)
    assert legacy_agent_path not in paths
    assert "/api/agents/{agent_id}/test-runs" not in paths


def test_openapi_includes_sop_quality_check_routes() -> None:
    contract = load_contract()
    paths = contract["paths"]
    schemas = contract["components"]["schemas"]

    expected_operations = {
        ("/api/sop-quality-checks", "get"): {"200", "401", "422"},
        ("/api/sop-quality-checks", "post"): {"200", "202", "401", "404", "502", "422"},
        ("/api/sop-quality-checks/{check_id}", "get"): {"200", "401", "404", "422"},
        ("/api/sop-quality-checks/{check_id}/events", "get"): {
            "200",
            "401",
            "404",
            "422",
        },
        ("/api/sop-quality-checks/{check_id}/stream", "get"): {
            "200",
            "401",
            "404",
            "422",
        },
    }

    for (path, method), statuses in expected_operations.items():
        operation = paths[path][method]
        assert operation["tags"] == ["sop-quality-checks"]
        assert statuses <= set(operation["responses"])

    assert {
        "SopQualityCheckStartResponse",
        "SopQualityCheckSummary",
        "SopQualityCheckDetail",
        "SopQualityDisplayState",
        "SopQualityCheckEvent",
    } <= set(schemas)
    assert "payload" not in schemas["SopQualityCheckEvent"]["properties"]


def test_agents_parameters_are_reusable_and_referenced() -> None:
    contract = load_contract()
    parameters = contract["components"]["parameters"]

    assert parameters["AgentId"] == {
        "name": "agent_id",
        "in": "path",
        "required": True,
        "schema": {"type": "string", "format": "uuid"},
    }
    assert parameters["AgentVersionNumber"] == {
        "name": "version_number",
        "in": "path",
        "required": True,
        "schema": {"type": "integer", "minimum": 1},
        "example": 1,
    }
    assert parameters["LlmProviderId"] == {
        "name": "provider_id",
        "in": "path",
        "required": True,
        "schema": {"type": "string", "format": "uuid"},
    }

    paths = contract["paths"]
    agent_id_ref = {"$ref": "#/components/parameters/AgentId"}
    version_ref = {"$ref": "#/components/parameters/AgentVersionNumber"}
    assert agent_id_ref in paths["/api/agents/{agent_id}"]["get"]["parameters"]
    assert agent_id_ref in paths["/api/agents/{agent_id}/draft"]["patch"][
        "parameters"
    ]
    assert version_ref in paths["/api/agents/{agent_id}/versions/{version_number}"][
        "get"
    ]["parameters"]
    provider_ref = {"$ref": "#/components/parameters/LlmProviderId"}
    assert provider_ref in paths["/api/v1/llm-providers/{provider_id}"]["get"][
        "parameters"
    ]


def test_agent_schemas_use_api_json_field_names() -> None:
    schemas = load_contract()["components"]["schemas"]

    for schema_name in (
        "AgentDraftConfig",
        "AgentCreate",
        "AgentDraftUpdate",
        "AgentSummary",
        "AgentDetail",
        "AgentVersionSummary",
        "AgentVersionDetail",
    ):
        assert schema_name in schemas

    draft_properties = schemas["AgentDraftConfig"]["properties"]
    assert "model_config" in draft_properties
    assert "model_parameters" not in draft_properties
    assert draft_properties["provider_id"] == {
        "type": "string",
        "format": "uuid",
        "nullable": True,
        "description": "Stored provider id. When set, model must be a bare model name without a provider prefix.",
    }
    assert schemas["AgentCreate"]["properties"]["draft"] == {
        "$ref": "#/components/schemas/AgentDraftConfig"
    }
    version_properties = schemas["AgentVersionDetail"]["properties"]
    assert "model_config" in version_properties
    assert "model_parameters" not in version_properties
    assert "provider_id" in version_properties


def test_llm_provider_schemas_are_documented_without_plaintext_api_key() -> None:
    schemas = load_contract()["components"]["schemas"]

    for schema_name in (
        "LlmProviderCreate",
        "LlmProviderUpdate",
        "LlmProviderSummary",
        "LlmProviderDetail",
        "LlmProviderModelTestRequest",
        "LlmProviderModelTestResponse",
    ):
        assert schema_name in schemas

    assert "api_key" in schemas["LlmProviderCreate"]["properties"]
    assert "api_key" in schemas["LlmProviderUpdate"]["properties"]
    assert "api_key" not in schemas["LlmProviderSummary"]["properties"]
    assert "api_key" not in schemas["LlmProviderDetail"]["properties"]
    assert "api_key_configured" in schemas["LlmProviderSummary"]["properties"]
    assert schemas["LlmProviderCreate"]["properties"]["models"] == {
        "type": "array",
        "items": {"type": "string"},
        "default": [],
        "description": "Model names this provider can serve.",
    }
    assert "models" in schemas["LlmProviderSummary"]["properties"]
    assert schemas["LlmProviderModelTestRequest"]["properties"]["model"] == {
        "type": "string",
        "minLength": 1,
    }
    assert schemas["LlmProviderModelTestResponse"]["properties"]["request"] == {
        "type": "object",
        "additionalProperties": True,
        "nullable": True,
    }
    assert schemas["LlmProviderModelTestResponse"]["properties"]["response"] == {
        "type": "object",
        "additionalProperties": True,
        "nullable": True,
    }
    provider_type_schema = schemas["LlmProviderCreate"]["properties"]["provider_type"]
    assert provider_type_schema["enum"] == [
        "openai",
        "anthropic",
        "azure_openai",
        "azure_ai",
        "google_vertexai",
        "google_genai",
        "anthropic_bedrock",
        "bedrock",
        "bedrock_converse",
        "cohere",
        "fireworks",
        "together",
        "mistralai",
        "huggingface",
        "groq",
        "ollama",
        "google_anthropic_vertex",
        "deepseek",
        "ibm",
        "nvidia",
        "xai",
        "openrouter",
        "perplexity",
        "upstage",
        "baseten",
        "litellm",
    ]
    assert schemas["LlmProviderUpdate"]["properties"]["provider_type"]["enum"] == (
        provider_type_schema["enum"]
    )
