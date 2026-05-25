from pathlib import Path

import yaml


def test_openapi_includes_mcp_server_routes() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text())
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
    assert paths["/api/mcp/servers"]["get"]["security"] == [
        {"McpAdminToken": []}
    ]

    lifecycle_responses = paths["/api/mcp/servers/{server_id}/start"]["post"][
        "responses"
    ]
    assert "502" in lifecycle_responses
