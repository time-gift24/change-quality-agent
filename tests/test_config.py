import pytest

from app.core.config import EnvironmentConfig, Settings


def test_settings_load_config_yaml(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    (tmp_path / "config.yaml").write_text(
        "\n".join(
            [
                "database_url: postgresql+asyncpg://config:config@db:5432/config_db",
                "environments:",
                "  - key: staging",
                "    name_zh: 预发",
                "    name_en: Staging",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings()

    assert settings.database_url == (
        "postgresql+asyncpg://config:config@db:5432/config_db"
    )
    assert settings.environments == [
        EnvironmentConfig(
            key="staging",
            name_zh="预发",
            name_en="Staging",
        )
    ]


def test_environment_config_has_no_sop_client_options() -> None:
    assert "sop_client_options" not in EnvironmentConfig.model_fields


def test_environment_variables_override_config_yaml(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://env:env@db:5432/env_db"
    )
    (tmp_path / "config.yaml").write_text(
        "database_url: postgresql+asyncpg://config:config@db:5432/config_db\n",
        encoding="utf-8",
    )

    settings = Settings()

    assert settings.database_url == "postgresql+asyncpg://env:env@db:5432/env_db"


def test_logging_settings_have_defaults() -> None:
    settings = Settings()

    assert settings.log_level == "INFO"
    assert settings.access_log_enabled is True


def test_logging_settings_can_be_overridden_by_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ACCESS_LOG_ENABLED", "false")

    settings = Settings()

    assert settings.log_level == "DEBUG"
    assert settings.access_log_enabled is False


def test_environment_lookup_by_key() -> None:
    settings = Settings(
        environments=[
            EnvironmentConfig(
                key="dev",
                name_zh="开发",
                name_en="Development",
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
