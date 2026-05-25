from mcp.server.fastmcp import FastMCP


mcp = FastMCP("echo")


@mcp.tool()
def echo_path(path: str) -> str:
    """Echo a path for MCP runtime integration tests."""
    return path


if __name__ == "__main__":
    mcp.run(transport="stdio")
