from secrets import token_urlsafe

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class EnvironmentConfig(BaseModel):
    key: str
    name_zh: str
    name_en: str

    def public_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "name_zh": self.name_zh,
            "name_en": self.name_en,
        }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        extra="ignore",
        yaml_file="config.yaml",
    )

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/" "change_quality_agent"
    )
    log_level: str = "INFO"
    access_log_enabled: bool = True
    auth_enabled: bool = True
    auth_dev_mode: bool = False
    auth_session_cookie_name: str = "cqa_user"
    auth_dev_common_refresh_token: str = Field(
        default_factory=lambda: token_urlsafe(32)
    )
    auth_dev_admin_refresh_token: str = Field(default_factory=lambda: token_urlsafe(32))
    environments: list[EnvironmentConfig] = Field(
        default_factory=lambda: [
            EnvironmentConfig(
                key="dev",
                name_zh="开发",
                name_en="Development",
            )
        ]
    )
    mcp_allowed_stdio_commands: list[str] = Field(default_factory=list)
    mcp_allowed_stdio_specs: list[str] = Field(default_factory=list)
    mcp_operation_timeout_seconds: float = 10.0
    mcp_runtime_single_instance: bool = False
    codeagent_base_url: str | None = None
    codeagent_token_provider: str = "codeagent"
    sop_quality_agent_id: str | None = None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )

    def get_environment(self, key: str) -> EnvironmentConfig:
        for environment in self.environments:
            if environment.key == key:
                return environment
        raise KeyError(key)


settings = Settings()
