import pytest

from app.core.config import EnvironmentConfig, Settings


def test_environment_lookup_by_key() -> None:
    settings = Settings(
        environments=[
            EnvironmentConfig(
                key="dev",
                name_zh="开发",
                name_en="Development",
                sop_client_options={"base_url": "https://dev.example.test"},
            )
        ]
    )

    env = settings.get_environment("dev")

    assert env.key == "dev"
    assert env.public_dict() == {
        "key": "dev",
        "name_zh": "开发",
        "name_en": "Development",
    }


def test_unknown_environment_raises_key_error() -> None:
    settings = Settings(environments=[])

    with pytest.raises(KeyError):
        settings.get_environment("prod")
