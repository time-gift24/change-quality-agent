import pytest

from app.agent.sop_quality.graph import build_sop_quality_graph


@pytest.mark.asyncio
async def test_sop_quality_graph_returns_result_for_valid_sop() -> None:
    graph = build_sop_quality_graph()

    result = await graph.ainvoke(
        {
            "check_id": "check-1",
            "sop_id": "release-checklist",
            "env_key": "dev",
            "sop_snapshot": {
                "sop_id": "release-checklist",
                "payload": {"title": "Release", "steps": [{"name": "deploy"}]},
            },
        }
    )

    assert result["quality_result"] in {"pass", "warn"}
    assert "result" in result
    assert result["result"]["quality_result"] == result["quality_result"]


@pytest.mark.asyncio
async def test_sop_quality_graph_flags_missing_steps() -> None:
    graph = build_sop_quality_graph()

    result = await graph.ainvoke(
        {
            "check_id": "check-1",
            "sop_id": "release-checklist",
            "env_key": "dev",
            "sop_snapshot": {
                "sop_id": "release-checklist",
                "payload": {"title": "Release"},
            },
        }
    )

    assert result["quality_result"] == "warn"
    assert result["findings"][0]["title"] == "Missing SOP steps"
