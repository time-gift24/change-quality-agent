"""Built-in tools available to configurable Agents."""

from dataclasses import dataclass

from langchain_core.tools import tool


@dataclass(frozen=True)
class BuiltinAgentTool:
    name: str
    label: str
    description: str | None
    enabled: bool = True
    implementation: object | None = None


@tool("echo")
def echo_tool(text: str) -> str:
    """Echo text back to the caller for local Agent testing."""
    return text


BUILTIN_AGENT_TOOLS: tuple[BuiltinAgentTool, ...] = (
    BuiltinAgentTool(
        name="echo",
        label="Echo",
        description="Echoes input text. Useful for validating Agent tool wiring.",
        implementation=echo_tool,
    ),
)

