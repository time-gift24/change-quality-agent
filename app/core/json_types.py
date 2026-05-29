from typing import TypeAlias

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | list[object] | dict[str, object]
JsonObject: TypeAlias = dict[str, JsonValue]
