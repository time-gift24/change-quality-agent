from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from app.core.json_types import JsonObject, to_json_object


class LlmModelParameters(BaseModel):
    model_config = ConfigDict(extra="allow")

    temperature: float | None = Field(default=None, ge=0)
    top_p: float | None = Field(default=None, ge=0, le=1)
    max_tokens: int | None = Field(default=None, ge=1)
    timeout: float | None = Field(default=None, gt=0)
    reasoning_effort: str | None = Field(default=None, min_length=1)
    model_kwargs: JsonObject | None = None


def dump_llm_model_parameters(
    parameters: LlmModelParameters | Mapping[str, object] | None,
) -> JsonObject:
    if parameters is None:
        return {}
    if isinstance(parameters, LlmModelParameters):
        raw = parameters.model_dump(mode="json", exclude_none=True)
    else:
        raw = LlmModelParameters.model_validate(dict(parameters)).model_dump(
            mode="json",
            exclude_none=True,
        )
    return to_json_object(raw)
