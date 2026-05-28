from typing import Any

from langgraph.graph import END, StateGraph

from app.agent.sop_quality.nodes.load_sop import load_sop
from app.agent.sop_quality.nodes.llm_check_steps import (
    make_llm_check_steps,
)
from app.agent.sop_quality.nodes.summarize_result import summarize_result
from app.agent.sop_quality.state import SopQualityState
from app.core.create_deepagents_by_llm_provider import create_deepagents_by_llm_provider


def build_sop_quality_graph(
    checkpointer: Any | None = None,
    *,
    llm_provider_repository: Any,
    create_deep_agent_by_provider=create_deepagents_by_llm_provider,
    on_live_event=None,
):
    builder = StateGraph(SopQualityState)
    builder.add_node("load_sop", load_sop)
    builder.add_node(
        "check_steps",
        make_llm_check_steps(
            llm_provider_repository,
            create_deep_agent_by_provider=create_deep_agent_by_provider,
            on_live_event=on_live_event,
        ),
    )
    builder.add_node("summarize_result", summarize_result)
    builder.set_entry_point("load_sop")
    builder.add_edge("load_sop", "check_steps")
    builder.add_edge("check_steps", "summarize_result")
    builder.add_edge("summarize_result", END)
    return builder.compile(checkpointer=checkpointer)
