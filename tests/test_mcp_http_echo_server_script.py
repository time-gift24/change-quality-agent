import importlib.util
from pathlib import Path

import pytest


def _load_script_module() -> object:
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "mcp_http_echo_server.py"
    )
    spec = importlib.util.spec_from_file_location("mcp_http_echo_server", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_mcp_http_echo_server_uses_streamable_http_path() -> None:
    module = _load_script_module()

    server = module.create_server(host="127.0.0.1", port=18000)

    assert server.settings.host == "127.0.0.1"
    assert server.settings.port == 18000
    assert server.settings.streamable_http_path == "/mcp"


@pytest.mark.asyncio
async def test_mcp_http_echo_server_exposes_echo_tool() -> None:
    module = _load_script_module()
    server = module.create_server()

    tools = await server.list_tools()
    result = await server.call_tool("echo", {"message": "hello"})

    assert [tool.name for tool in tools] == ["echo"]
    assert result[0][0].text == "hello"
