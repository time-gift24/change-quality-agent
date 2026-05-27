"""Deprecated compatibility wrapper for the SOP quality mock graph."""

from agent.sop_quality.graph import (
    build_sop_quality_graph,
    run_mock_sop_quality_graph,
    stream_mock_sop_quality_graph,
    validate_sop_snapshot,
)

__all__ = [
    "build_sop_quality_graph",
    "run_mock_sop_quality_graph",
    "stream_mock_sop_quality_graph",
    "validate_sop_snapshot",
]
