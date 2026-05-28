from app.agent.sop_quality.state import SopQualityState
from app.services.sop_client import SopClient


def make_load_sop(sop_client: SopClient):
    async def load_sop(state: SopQualityState) -> SopQualityState:
        sop_id = state.get("sop_id") or state.get("sop_snapshot", {}).get("sop_id", "")
        env_key = state.get("env_key") or state.get("sop_snapshot", {}).get("env_key", "")
        snapshot = await sop_client.get_sop(sop_id, env_key)
        return {
            "sop_snapshot": snapshot.model_dump(mode="json"),
            "messages": [
                {
                    "role": "assistant",
                    "content": f"Loaded SOP {sop_id}.",
                }
            ],
        }

    return load_sop
