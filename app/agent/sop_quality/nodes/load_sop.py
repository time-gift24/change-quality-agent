from app.agent.sop_quality.state import SopQualityState


async def load_sop(state: SopQualityState) -> SopQualityState:
    sop_id = state.get("sop_id") or state.get("sop_snapshot", {}).get("sop_id", "")
    return {
        "messages": [
            {
                "role": "assistant",
                "content": f"Loaded SOP {sop_id}.",
            }
        ]
    }
