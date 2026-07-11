from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_process_environment_overrides_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=sqlite:///from-dotenv.db\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///from-process.db")

    settings = Settings(_env_file=env_file)

    assert settings.database_url == "sqlite:///from-process.db"


def test_development_default_database_is_independent_of_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.chdir(tmp_path)

    settings = Settings(_env_file=None)

    assert settings.database_url == f"sqlite:///{Path(__file__).parents[1] / 'dev.db'}"


def test_production_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)

    with pytest.raises(ValidationError, match="DATABASE_URL must be set"):
        Settings(_env_file=None, app_env="production")
