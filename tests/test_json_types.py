from pydantic import BaseModel

from app.core.json_types import to_json_object


class ExamplePayload(BaseModel):
    name: str
    count: int


def test_to_json_object_converts_structured_values_at_json_boundary() -> None:
    payload = to_json_object(
        {
            "nested": ExamplePayload(name="review", count=2),
            "items": (1, True, None),
            "opaque": object(),
        }
    )

    assert payload["nested"] == {"name": "review", "count": 2}
    assert payload["items"] == [1, True, None]
    assert isinstance(payload["opaque"], str)
