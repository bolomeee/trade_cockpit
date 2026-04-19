from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to this file so it works regardless of CWD.
# backend/app/config.py → go up 2 levels → project root
_ENV_FILE = Path(__file__).parent.parent.parent / ".env"


class Settings(BaseSettings):
    database_url: str = "sqlite:///./dev.db"
    fmp_api_key: str = ""  # D034: primary external data source
    polygon_api_key: str = ""  # legacy, kept as D034 rollback anchor
    app_env: str = "development"

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")


settings = Settings()
