from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: SecretStr
    tavily_api_key: SecretStr

    log_level: str = "INFO"
    agent_model: str = "claude-sonnet-4-6"
    agent_max_iterations: int = Field(default=8, ge=1, le=20)
    http_timeout_seconds: float = Field(default=20.0, gt=0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
