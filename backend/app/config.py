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

    # F216-e weekly stage refresh (weekdays 22:20 UTC, after regime at 22:15, before setup at 22:30)
    weekly_stage_cron_hour: int = 22
    weekly_stage_cron_minute: int = 20

    # F211-d2 journal monthly review cron (1st of month 06:00 UTC, after universe at 05:00)
    journal_monthly_cron_day: int = 1
    journal_monthly_cron_hour: int = 6
    journal_monthly_cron_minute: int = 0

    # v2.0 F208 AI Gateway (D064 / D069)
    ai_model_default: str = "gpt-5.4-nano"      # default tier (F209 / F211 contradiction/news)
    ai_model_critical: str = "gpt-5.4-mini"     # critical tier (F210)
    ai_model_complex: str = "gpt-5.4"           # complex tier (F211 journal_assistant)
    openai_api_key: str = ""                    # F208-c 调用 LiteLLM 时使用
    ai_monthly_budget_usd: float = 20.0         # 月度熔断阈值 (D069)
    ai_memo_cache_ttl_hours: int = 24           # memo dedup 命中窗口 (D069)
    ai_schema_version: str = "v1"              # schema 失效旗标 (D069)
    # F211-a2 per-task model override (D075)
    ai_task_overrides_json: str = ""  # JSON dict: task_type → {model, base_url, api_key, input_cost_per_1m, output_cost_per_1m}

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")


settings = Settings()
