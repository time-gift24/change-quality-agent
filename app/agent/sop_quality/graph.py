from typing import Any

from langgraph.graph import END, StateGraph

from app.agent.sop_quality.nodes.load_sop import make_load_sop
from app.agent.sop_quality.nodes.review_sop import make_review_sop
from app.agent.sop_quality.nodes.submit_result import (
    make_submit_result,
    mock_submit_quality_result,
)
from app.agent.sop_quality.nodes.summarize_result import make_summarize_result
from app.agent.sop_quality.state import SopQualityState
from app.core.agent_streaming import DeepAgentStreamRunner
from app.services.sop_client import MockSopClient


class _NoopMessageWriter:
    async def append_step_message(
        self,
        *,
        step: str,
        role: str,
        content: str,
        additional_kwargs: dict[str, Any] | None = None,
    ) -> Any:
        class _Msg:
            sequence = 0

        return _Msg()


def build_sop_quality_graph(
    checkpointer: Any | None = None,
    *,
    sop_client: Any | None = None,
    agent_factory: Any,
    submit_quality_result: object = mock_submit_quality_result,
    message_writer: Any | None = None,
    deepagent_stream_runner: Any | None = None,
    live_event_publisher: Any | None = None,
) -> object:
    writer = message_writer or _NoopMessageWriter()
    runner = deepagent_stream_runner or DeepAgentStreamRunner(
        message_writer=writer,
        live_event_publisher=live_event_publisher,
    )

    builder = StateGraph(SopQualityState)
    builder.add_node("load_sop", make_load_sop(sop_client or MockSopClient(), writer))
    builder.add_node(
        "review_sop",
        make_review_sop(agent_factory.create_deepagents, runner),
    )
    builder.add_node("summarize_result", make_summarize_result(writer))
    builder.add_node(
        "submit_result",
        make_submit_result(submit_quality_result, writer),
    )
    builder.set_entry_point("load_sop")
    builder.add_edge("load_sop", "review_sop")
    builder.add_edge("review_sop", "summarize_result")
    builder.add_edge("summarize_result", "submit_result")
    builder.add_edge("submit_result", END)
    return builder.compile(checkpointer=checkpointer)
