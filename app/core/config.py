from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvironmentConfig(BaseModel):
    key: str
    name_zh: str
    name_en: str
    sop_client_options: dict[str, str] = Field(default_factory=dict)

    def public_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "name_zh": self.name_zh,
            "name_en": self.name_en,
        }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore")

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/"
        "change_quality_agent"
    )
    environments: list[EnvironmentConfig] = Field(
        default_factory=lambda: [
            EnvironmentConfig(
                key="dev",
                name_zh="开发",
                name_en="Development",
                sop_client_options={},
            )
        ]
    )

    def get_environment(self, key: str) -> EnvironmentConfig:
        for environment in self.environments:
            if environment.key == key:
                return environment
        raise KeyError(key)


settings = Settings()
