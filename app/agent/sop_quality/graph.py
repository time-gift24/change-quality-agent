from typing import Any

from langgraph.graph import END, StateGraph

from app.agent.sop_quality.nodes.load_sop import make_load_sop
from app.agent.sop_quality.nodes.review_sop import make_review_sop
from app.agent.sop_quality.nodes.summarize_result import make_summarize_result
from app.agent.sop_quality.nodes.submit_result import (
    mock_submit_quality_result,
    make_submit_result,
)
from app.agent.sop_quality.state import SopQualityState
from app.core.create_deepagents_by_llm_provider import create_deepagents_by_llm_provider
from app.services.sop_client import MockSopClient


def build_sop_quality_graph(
    checkpointer: Any | None = None,
    *,
    sop_client: Any | None = None,
    llm_provider_repository: Any,
    create_deep_agent_by_provider=create_deepagents_by_llm_provider,
    submit_quality_result=mock_submit_quality_result,
    on_live_event=None,
):
    builder = StateGraph(SopQualityState)
    builder.add_node("load_sop", make_load_sop(sop_client or MockSopClient()))
    builder.add_node(
        "review_sop",
        make_review_sop(
            llm_provider_repository,
            create_deep_agent_by_provider=create_deep_agent_by_provider,
            on_live_event=on_live_event,
        ),
    )
    builder.add_node("summarize_result", make_summarize_result(on_live_event))
    builder.add_node(
        "submit_result",
        make_submit_result(submit_quality_result, on_live_event=on_live_event),
    )
    builder.set_entry_point("load_sop")
    builder.add_edge("load_sop", "review_sop")
    builder.add_edge("review_sop", "summarize_result")
    builder.add_edge("summarize_result", "submit_result")
    builder.add_edge("submit_result", END)
    return builder.compile(checkpointer=checkpointer)
