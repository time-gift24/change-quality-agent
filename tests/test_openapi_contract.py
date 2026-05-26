from pathlib import Path

import yaml


CONTRACT_PATH = Path(__file__).resolve().parents[1] / "api" / "openapi.yml"


def load_contract() -> dict:
    return yaml.safe_load(CONTRACT_PATH.read_text())


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
            responses = paths[path][method]["responses"]
            assert "403" in responses
            assert "503" in responses

    schemas = spec["components"]["schemas"]
    assert {
        "McpServerCreate",
        "McpServerUpdate",
        "McpServerSummary",
        "McpServerDetail",
        "McpLifecycleResponse",
    } <= set(schemas)
    assert spec["components"]["securitySchemes"]["McpAdminToken"] == {
        "type": "apiKey",
        "in": "header",
        "name": "X-MCP-Admin-Token",
    }
    assert paths["/api/mcp/servers"]["get"]["security"] == [{"McpAdminToken": []}]

    lifecycle_responses = paths["/api/mcp/servers/{server_id}/start"]["post"][
        "responses"
    ]
    assert "502" in lifecycle_responses


def test_agents_tag_and_paths_are_documented() -> None:
    contract = load_contract()

    tag_descriptions = {tag["name"]: tag["description"] for tag in contract["tags"]}
    assert tag_descriptions["agents"] == (
        "ReAct agent definitions, versions, and test runs."
    )

    paths = contract["paths"]
    expected_operations = {
        ("/api/agents", "get"): {"200", "422"},
        ("/api/agents", "post"): {"201", "409", "422"},
        ("/api/agents/{agent_key}", "get"): {"200", "404", "422"},
        ("/api/agents/{agent_key}", "delete"): {"204", "404", "422"},
        ("/api/agents/{agent_key}/draft", "patch"): {"200", "404", "422"},
        ("/api/agents/{agent_key}/publish", "post"): {
            "201",
            "400",
            "404",
            "422",
        },
        ("/api/agents/{agent_key}/versions", "get"): {"200", "404", "422"},
        ("/api/agents/{agent_key}/versions/{version_number}", "get"): {
            "200",
            "404",
            "422",
        },
        ("/api/agents/{agent_key}/test-runs", "post"): {"202", "400", "404", "422"},
    }

    for (path, method), statuses in expected_operations.items():
        operation = paths[path][method]
        assert operation["tags"] == ["agents"]
        assert statuses <= set(operation["responses"])


def test_agents_parameters_are_reusable_and_referenced() -> None:
    contract = load_contract()
    parameters = contract["components"]["parameters"]

    assert parameters["AgentKey"] == {
        "name": "agent_key",
        "in": "path",
        "required": True,
        "schema": {"type": "string"},
        "example": "release-reviewer",
    }
    assert parameters["AgentVersionNumber"] == {
        "name": "version_number",
        "in": "path",
        "required": True,
        "schema": {"type": "integer", "minimum": 1},
        "example": 1,
    }

    paths = contract["paths"]
    agent_key_ref = {"$ref": "#/components/parameters/AgentKey"}
    version_ref = {"$ref": "#/components/parameters/AgentVersionNumber"}
    assert agent_key_ref in paths["/api/agents/{agent_key}"]["get"]["parameters"]
    assert agent_key_ref in paths["/api/agents/{agent_key}/draft"]["patch"][
        "parameters"
    ]
    assert version_ref in paths["/api/agents/{agent_key}/versions/{version_number}"][
        "get"
    ]["parameters"]


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
        "AgentMessage",
        "AgentTestRunCreate",
    ):
        assert schema_name in schemas

    draft_properties = schemas["AgentDraftConfig"]["properties"]
    assert "model_config" in draft_properties
    assert "model_parameters" not in draft_properties
    assert schemas["AgentCreate"]["properties"]["draft"] == {
        "$ref": "#/components/schemas/AgentDraftConfig"
    }
    assert schemas["AgentTestRunCreate"]["properties"]["messages"]["items"] == {
        "$ref": "#/components/schemas/AgentMessage"
    }

    version_properties = schemas["AgentVersionDetail"]["properties"]
    assert "model_config" in version_properties
    assert "model_parameters" not in version_properties


def test_agent_test_runs_response_reuses_run_start_response() -> None:
    contract = load_contract()

    responses = contract["paths"]["/api/agents/{agent_key}/test-runs"]["post"][
        "responses"
    ]
    response_schema = responses["202"]["content"]["application/json"]["schema"]
    assert response_schema == {"$ref": "#/components/schemas/RunStartResponse"}
    assert responses["400"]["description"] == (
        "Agent is disabled or requested agent version was not found."
    )


def test_llm_provider_paths_are_documented() -> None:
    contract = load_contract()
    paths = contract["paths"]
    admin_security = [{"FakeUserHeaders": [], "FakeUserRole": []}]

    expected_operations = {
        ("/api/llm-providers", "get"): {"200", "401", "422"},
        ("/api/llm-providers", "post"): {"201", "401", "409", "422"},
        ("/api/llm-providers/{provider_id}", "get"): {"200", "401", "404", "422"},
        ("/api/llm-providers/{provider_id}", "patch"): {
            "200",
            "401",
            "404",
            "409",
            "422",
        },
        ("/api/llm-providers/{provider_id}", "delete"): {
            "204",
            "401",
            "404",
            "422",
        },
        ("/api/admin/llm-providers", "get"): {"200", "401", "403", "422"},
        ("/api/admin/llm-providers", "post"): {"201", "401", "403", "409", "422"},
        ("/api/admin/llm-providers/{provider_id}", "get"): {
            "200",
            "401",
            "403",
            "404",
            "422",
        },
        ("/api/admin/llm-providers/{provider_id}", "patch"): {
            "200",
            "401",
            "403",
            "404",
            "409",
            "422",
        },
        ("/api/admin/llm-providers/{provider_id}", "delete"): {
            "204",
            "401",
            "403",
            "404",
            "422",
        },
    }

    for (path, method), statuses in expected_operations.items():
        operation = paths[path][method]
        assert statuses <= set(operation["responses"])

    assert paths["/api/llm-providers"]["get"]["security"] == [
        {"FakeUserHeaders": []}
    ]
    assert paths["/api/llm-providers/{provider_id}"]["patch"]["parameters"] == [
        {"$ref": "#/components/parameters/ProviderId"}
    ]
    assert paths["/api/admin/llm-providers/{provider_id}"]["delete"][
        "parameters"
    ] == [{"$ref": "#/components/parameters/ProviderId"}]
    for path, methods in paths.items():
        if not path.startswith("/api/admin/llm-providers"):
            continue
        for operation in methods.values():
            assert operation["security"] == admin_security

    security_schemes = contract["components"]["securitySchemes"]
    assert security_schemes["FakeUserHeaders"] == {
        "type": "apiKey",
        "in": "header",
        "name": "X-User-Id",
    }
    assert security_schemes["FakeUserRole"] == {
        "type": "apiKey",
        "in": "header",
        "name": "X-User-Role",
    }


def test_llm_provider_schemas_do_not_expose_secrets() -> None:
    schemas = load_contract()["components"]["schemas"]

    assert {"LlmProviderCreate", "LlmProviderUpdate", "LlmProviderDetail"} <= set(
        schemas
    )
    assert "api_key" in schemas["LlmProviderCreate"]["properties"]
    assert "api_key" in schemas["LlmProviderUpdate"]["properties"]
    update_properties = schemas["LlmProviderUpdate"]["properties"]
    for field_name in ["name", "api_key", "metadata", "is_active"]:
        assert update_properties[field_name].get("nullable") is not True
        assert "default" not in update_properties[field_name]
    for field_name in ["provider", "base_url", "model"]:
        assert update_properties[field_name]["nullable"] is True

    detail_schema = schemas["LlmProviderDetail"]
    assert {
        "id",
        "name",
        "provider",
        "base_url",
        "api_key_hint",
        "model",
        "metadata",
        "is_active",
        "created_at",
        "updated_at",
    } <= set(detail_schema["required"])

    detail_properties = detail_schema["properties"]
    assert "api_key_hint" in detail_properties
    assert "api_key" not in detail_properties
    assert "api_key_ciphertext" not in detail_properties
