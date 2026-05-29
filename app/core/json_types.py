import json
from collections.abc import Mapping
from typing import TypeAlias, cast

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | list[object] | dict[str, object]
JsonObject: TypeAlias = dict[str, JsonValue]


def to_json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Mapping):
        return {str(key): to_json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [to_json_value(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if model_dump is not None:
        try:
            return to_json_value(model_dump(mode="json"))
        except TypeError:
            return to_json_value(model_dump())
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    try:
        json.dumps(value)
    except TypeError:
        return repr(value)
    return cast(JsonValue, value)


def to_json_object(value: Mapping[str, object]) -> JsonObject:
    return {str(key): to_json_value(item) for key, item in value.items()}
