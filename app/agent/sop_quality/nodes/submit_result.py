import inspect
from collections.abc import Callable

from app.agent.sop_quality.state import SopQualityState
from app.core.agent_streaming import SessionMessageWriter
from app.core.json_types import JsonObject, JsonValue

SubmitQualityResult = Callable[[JsonObject], object]


async def mock_submit_quality_result(payload: JsonObject) -> JsonObject:
    return {
        "external_status": "mock_submitted",
        "check_id": payload.get("check_id"),
    }


def make_submit_result(
    submit_quality_result: SubmitQualityResult,
    message_writer: SessionMessageWriter,
):
    async def submit_result(state: SopQualityState) -> SopQualityState:
        result = state.get("result")
        if not isinstance(result, dict):
            raise ValueError("SOP quality result is missing before submission.")

        payload = {
            "check_id": state.get("check_id"),
            "sop_id": state.get("sop_id"),
            "env_key": state.get("env_key"),
            "sop_snapshot": state.get("sop_snapshot") or {},
            **result,
        }
        submission = submit_quality_result(payload)
        if inspect.isawaitable(submission):
            submission = await submission
        submission_result = _json_safe(submission)
        await message_writer.append_step_message(
            step="submit_result",
            role="assistant",
            content=_submission_text(submission_result),
            additional_kwargs={
                "kind": "step_message",
                "step": "submit_result",
                "channel": "summary",
            },
        )
        return {
            "submission_result": submission_result,
            "result": {
                **result,
                "submission_result": submission_result,
            },
        }

    return submit_result


def _submission_text(submission_result: object) -> str:
    if isinstance(submission_result, dict):
        status = submission_result.get("external_status") or submission_result.get("status")
        return f"External submission: {status or 'completed'}."
    return "External submission completed."


def _json_safe(value: object) -> JsonValue:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return repr(value)
