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

    # F105 cron schedule (D038 universe monthly refresh; D042 independent scanner)
    scanner_cron_hour: int = 6
    scanner_cron_minute: int = 15
    universe_cron_day: int = 1
    universe_cron_hour: int = 5
    universe_cron_minute: int = 0

    # F204-b earnings calendar refresh (weekdays 05:30 UTC, before scanner)
    earnings_cron_hour: int = 5
    earnings_cron_minute: int = 30

    # F201-b regime ETF refresh + scoring (weekdays 22:15 UTC, after main refresh at 21:30)
    regime_cron_hour: int = 22
    regime_cron_minute: int = 15

    # F202-b setup snapshot scan (weekdays 22:30 UTC, after regime at 22:15)
    setup_cron_hour: int = 22
    setup_cron_minute: int = 30

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")


settings = Settings()
