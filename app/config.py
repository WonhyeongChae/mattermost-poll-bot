from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./poll_bot.db"
    public_base_url: str = "http://localhost:8000"
    mattermost_base_url: str = "https://meeting.ssafy.com"
    mattermost_bot_token: str = ""
    mattermost_command_token: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
