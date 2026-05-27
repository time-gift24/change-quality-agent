from collections.abc import AsyncIterator
from typing import Any

from app.agent.sop_quality.prompts.system_prompts import build_sop_quality_user_message
from app.core.agent_runtime import AgentRuntime

SOP_QUALITY_AGENT_KEY = "sop-quality-v1"


async def stream_sop_quality_agent(
    *,
    runtime: AgentRuntime,
    version: Any,
    run: Any,
) -> AsyncIterator[dict[str, Any]]:
    messages = [build_sop_quality_user_message(run)]
    async for event in runtime.stream(version=version, messages=messages):
        yield event
