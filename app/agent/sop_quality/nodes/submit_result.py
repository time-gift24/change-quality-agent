import inspect
from collections.abc import Callable
from typing import Any

from app.agent.sop_quality.state import SopQualityState

SubmitQualityResult = Callable[[dict[str, Any]], Any]
LiveEventCallback = Callable[[dict[str, Any]], Any]


async def mock_submit_quality_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "external_status": "mock_submitted",
        "check_id": payload.get("check_id"),
    }


def make_submit_result(
    submit_quality_result: SubmitQualityResult = mock_submit_quality_result,
    on_live_event: LiveEventCallback | None = None,
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
        await _publish_live_event(
            on_live_event,
            {
                "type": "messages",
                "node": "submit_result",
                "channel": "summary",
                "message": _submission_text(submission_result),
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


async def _publish_live_event(
    on_live_event: LiveEventCallback | None,
    event: dict[str, Any],
) -> None:
    if on_live_event is None:
        return
    result = on_live_event(event)
    if inspect.isawaitable(result):
        await result


def _submission_text(submission_result: Any) -> str:
    if isinstance(submission_result, dict):
        status = submission_result.get("external_status") or submission_result.get("status")
        return f"External submission: {status or 'completed'}."
    return "External submission completed."


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return repr(value)
