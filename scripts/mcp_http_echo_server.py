from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP


def create_server(
    *,
    host: str = "127.0.0.1",
    port: int = 18000,
    path: str = "/mcp",
) -> FastMCP:
    server = FastMCP(
        "echo",
        host=host,
        port=port,
        streamable_http_path=path,
    )

    @server.tool()
    def echo(message: str) -> str:
        """Return the input message unchanged."""
        return message

    return server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a local streamable HTTP MCP echo server.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18000)
    parser.add_argument("--path", default="/mcp")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = create_server(host=args.host, port=args.port, path=args.path)
    server.run(transport="streamable-http")


if __name__ == "__main__":
    main()
