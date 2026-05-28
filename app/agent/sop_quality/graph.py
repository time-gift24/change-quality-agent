from typing import Any

from langgraph.graph import END, StateGraph

from app.agent.sop_quality.nodes.check_steps import check_steps
from app.agent.sop_quality.nodes.load_sop import load_sop
from app.agent.sop_quality.nodes.summarize_result import summarize_result
from app.agent.sop_quality.state import SopQualityState


def build_sop_quality_graph(checkpointer: Any | None = None):
    builder = StateGraph(SopQualityState)
    builder.add_node("load_sop", load_sop)
    builder.add_node("check_steps", check_steps)
    builder.add_node("summarize_result", summarize_result)
    builder.set_entry_point("load_sop")
    builder.add_edge("load_sop", "check_steps")
    builder.add_edge("check_steps", "summarize_result")
    builder.add_edge("summarize_result", END)
    return builder.compile(checkpointer=checkpointer)
