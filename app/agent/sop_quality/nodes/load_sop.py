from app.agent.sop_quality.state import SopQualityState
from app.core.agent_streaming import SessionMessageWriter
from app.services.sop_client import SopClient


def make_load_sop(
    sop_client: SopClient, message_writer: SessionMessageWriter
) -> object:
    async def load_sop(state: SopQualityState) -> SopQualityState:
        sop_id = state.get("sop_id") or state.get("sop_snapshot", {}).get("sop_id", "")
        env_key = state.get("env_key") or state.get("sop_snapshot", {}).get(
            "env_key", ""
        )
        snapshot = await sop_client.get_sop(sop_id, env_key)
        content = f"Loaded SOP {sop_id}."
        await message_writer.append_step_message(
            step="load_sop",
            role="assistant",
            content=content,
            additional_kwargs={"kind": "step_message", "step": "load_sop"},
        )
        return {
            "sop_snapshot": snapshot.model_dump(mode="json"),
            "messages": [
                {
                    "role": "assistant",
                    "content": content,
                }
            ],
        }

    return load_sop
