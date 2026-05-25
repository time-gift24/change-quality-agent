from pathlib import Path

import yaml


def test_openapi_includes_mcp_server_routes() -> None:
    spec = yaml.safe_load(Path("api/openapi.yml").read_text())
    paths = spec["paths"]

    assert "/api/mcp/servers" in paths
    assert "/api/mcp/servers/{server_id}" in paths
    assert "/api/mcp/servers/{server_id}/start" in paths
    assert "/api/mcp/servers/{server_id}/check" in paths
