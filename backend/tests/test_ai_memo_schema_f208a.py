"""F208-a schema tests: AiMemo ORM + alembic 012 + Settings AI fields."""
from __future__ import annotations

import os
import sqlite3
import tempfile
from decimal import Decimal
from datetime import datetime, timezone

import pytest
from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Session

from app.models import AiMemo, Base
from app.models.ai_memo import AiMemo as AiMemoClass


# ---------------------------------------------------------------------------
# Test 1: ORM columns match DATA-MODEL §AiMemo (13 columns)
# ---------------------------------------------------------------------------

_EXPECTED_COLUMNS = {
    "id": (Integer, False),
    "task_type": (String, False),
    "input_hash": (String, False),
    "input_json": (Text, False),
    "output_json": (Text, False),
    "schema_version": (String, False),
    "model_used": (String, False),
    "tier": (String, False),
    "tokens_in": (Integer, False),
    "tokens_out": (Integer, False),
    "cost_usd": (Numeric, False),
    "latency_ms": (Integer, False),
    "created_at": (DateTime, False),
}


def test_ai_memo_columns_match_data_model() -> None:
    cols = {c.name: c for c in AiMemoClass.__table__.columns}
    assert set(cols.keys()) == set(_EXPECTED_COLUMNS.keys()), (
        f"column name mismatch: got {set(cols.keys())}"
    )
    for name, (expected_type_cls, expected_nullable) in _EXPECTED_COLUMNS.items():
        col = cols[name]
        assert isinstance(col.type, expected_type_cls), (
            f"{name}: expected {expected_type_cls.__name__}, got {type(col.type).__name__}"
        )
        # id is primary key — SQLAlchemy sets nullable=False automatically
        if name != "id":
            assert col.nullable == expected_nullable, (
                f"{name}: expected nullable={expected_nullable}, got {col.nullable}"
            )


# ---------------------------------------------------------------------------
# Test 2: alembic upgrade head creates ai_memos + composite indexes
# ---------------------------------------------------------------------------

def _run_alembic_with_temp_db():
    """Helper: returns (tmp_dir_path, db_path, alembic Config)."""
    from alembic.config import Config

    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test_012.db")
    ini_path = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    cfg = Config(os.path.abspath(ini_path))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return tmp, db_path, cfg


def test_alembic_upgrade_creates_ai_memos_table() -> None:
    import shutil
    from alembic import command

    tmp, db_path, cfg = _run_alembic_with_temp_db()
    try:
        command.upgrade(cfg, "head")
        conn = sqlite3.connect(db_path)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
        conn.close()

        assert "ai_memos" in tables, f"ai_memos table not found; tables={tables}"
        assert "ix_ai_memos_task_input_created" in indexes, f"dedup index missing; indexes={indexes}"
        assert "ix_ai_memos_created_at_desc" in indexes, f"budget index missing; indexes={indexes}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test 3: downgrade removes ai_memos; re-upgrade restores it (idempotent)
# ---------------------------------------------------------------------------

def test_alembic_downgrade_removes_ai_memos() -> None:
    import shutil
    from alembic import command

    tmp, db_path, cfg = _run_alembic_with_temp_db()
    try:
        command.upgrade(cfg, "head")
        # Downgrade past 012 (ai_memos) to 011 (user_settings) to verify ai_memos is removed
        command.downgrade(cfg, "011_f203b1_user_settings")

        conn = sqlite3.connect(db_path)
        tables_after = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        assert "ai_memos" not in tables_after, f"ai_memos still present after downgrade; tables={tables_after}"

        # re-upgrade: idempotent
        command.upgrade(cfg, "head")
        conn = sqlite3.connect(db_path)
        tables_final = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        assert "ai_memos" in tables_final, "ai_memos missing after re-upgrade"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test 4: write/read roundtrip — Numeric precision preserved
# ---------------------------------------------------------------------------

def test_ai_memo_write_read_roundtrip(db_session: Session) -> None:
    memo = AiMemo(
        task_type="contradiction",
        input_hash="abc123" * 10 + "ab",  # 62 chars, within String(64)
        input_json='{"ticker":"AAPL"}',
        output_json='{"result":"ok"}',
        schema_version="v1",
        model_used="gpt-5.4-nano",
        tier="default",
        tokens_in=100,
        tokens_out=50,
        cost_usd=Decimal("0.012340"),
        latency_ms=312,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db_session.add(memo)
    db_session.commit()

    result = (
        db_session.query(AiMemo)
        .filter_by(task_type="contradiction", input_hash=memo.input_hash)
        .one()
    )
    assert result.cost_usd == Decimal("0.012340"), (
        f"Numeric precision lost: got {result.cost_usd!r}"
    )
    assert result.task_type == "contradiction"
    assert result.tokens_in == 100


# ---------------------------------------------------------------------------
# Test 5: Settings loads AI env overrides via monkeypatch
# ---------------------------------------------------------------------------

def test_settings_loads_ai_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_MODEL_DEFAULT", "claude-haiku-4-5")
    monkeypatch.setenv("AI_MONTHLY_BUDGET_USD", "50.0")
    monkeypatch.setenv("AI_SCHEMA_VERSION", "v2")

    # Import fresh Settings instance (bypass module-level singleton)
    from app.config import Settings
    s = Settings()

    assert s.ai_model_default == "claude-haiku-4-5"
    assert s.ai_monthly_budget_usd == 50.0
    assert s.ai_schema_version == "v2"
    # Unset fields keep defaults
    assert s.ai_model_critical == "gpt-5.4-mini"
    assert s.ai_memo_cache_ttl_hours == 24
