"""Runtime configuration for the agent platform."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings sourced from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_name: str = Field(default="Agent Platform", validation_alias="PROJECT_NAME")
    openai_api_key: Optional[str] = Field(default=None, validation_alias="OPENAI_API_KEY")
    ollama_host: Optional[str] = Field(default="http://localhost:11434", validation_alias="OLLAMA_HOST")
    llm_primary: str = Field(default="openai", validation_alias="LLM_PRIMARY")
    llm_timeout: float = Field(default=45.0, validation_alias="LLM_TIMEOUT")
    llm_max_retries: int = Field(default=3, validation_alias="LLM_MAX_RETRIES")
    llm_circuit_breaker_threshold: int = Field(
        default=5, validation_alias="LLM_CIRCUIT_BREAKER_THRESHOLD"
    )
    default_timezone: str = Field(default="UTC", validation_alias="DEFAULT_TIMEZONE")
    data_root: str = Field(default="data", validation_alias="DATA_ROOT")
    audit_log_path: str = Field(default="logs/audit.log", validation_alias="AUDIT_LOG_PATH")


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
