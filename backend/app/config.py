from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[1] / ".env", extra="ignore")

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    jira_base_url: str | None = None
    jira_username: str | None = None
    jira_api_token: str | None = None
    repository_path: str | None = None
    github_token: str | None = None
    github_repository: str | None = None
    github_base_branch: str = "main"
    llm_provider: str = "gemini"


@lru_cache
def get_settings() -> Settings:
    return Settings()
