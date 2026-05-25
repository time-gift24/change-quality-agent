from typing import Any

from langgraph.graph import END, START, StateGraph

from agent.state import SopQualityState


def validate_sop_snapshot(state: SopQualityState) -> dict[str, str]:
    sop_snapshot = state.get("sop_snapshot")
    if not isinstance(sop_snapshot, dict) or not sop_snapshot.get("payload"):
        raise ValueError("SOP snapshot payload is required")
    return {"status": "mock_success"}


def build_sop_quality_graph():
    graph = StateGraph(SopQualityState)
    graph.add_node("validate_sop", validate_sop_snapshot)
    graph.add_edge(START, "validate_sop")
    graph.add_edge("validate_sop", END)
    return graph.compile()


async def run_mock_sop_quality_graph(
    *,
    run_id: str,
    sop_snapshot: dict[str, Any],
) -> dict[str, Any]:
    graph = build_sop_quality_graph()
    result = await graph.ainvoke(
        {
            "run_id": run_id,
            "sop_snapshot": sop_snapshot,
        }
    )
    return {"status": result["status"]}
