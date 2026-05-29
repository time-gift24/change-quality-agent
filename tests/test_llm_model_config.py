from app.core.llm_model_config import LlmModelParameters, dump_llm_model_parameters


def test_dump_llm_model_parameters_omits_unset_fields_and_keeps_extensions() -> None:
    payload = dump_llm_model_parameters(
        LlmModelParameters(
            temperature=0,
            reasoning_effort="high",
            model_kwargs={"stream_options": {"include_usage": True}},
        )
    )

    assert payload == {
        "temperature": 0,
        "reasoning_effort": "high",
        "model_kwargs": {"stream_options": {"include_usage": True}},
    }


def test_dump_llm_model_parameters_validates_raw_mapping_before_json_dump() -> None:
    payload = dump_llm_model_parameters(
        {
            "temperature": 0.2,
            "provider_extension": {"enabled": True},
        }
    )

    assert payload == {
        "temperature": 0.2,
        "provider_extension": {"enabled": True},
    }
