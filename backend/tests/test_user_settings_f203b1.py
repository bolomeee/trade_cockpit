"""F203-b1 UserSettings data/access layer tests — Sprint Contract S1–S13."""
from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.models.user_settings import UserSettings
from app.repositories.user_settings_repository import UserSettingsRepository

# ── in-memory DB fixtures ──────────────────────────────────────────────────────


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def repo(db: Session) -> UserSettingsRepository:
    return UserSettingsRepository(db)


# ── S1: get() empty → None; get() after insert → ORM instance ─────────────────


def test_s1_get_empty_returns_none(repo: UserSettingsRepository) -> None:
    assert repo.get() is None


def test_s1_get_after_insert_returns_row(db: Session, repo: UserSettingsRepository) -> None:
    row = UserSettings(
        id=1,
        account_size=100000.0,
        max_exposure_pct=80.0,
        single_trade_risk_pct=1.0,
        default_risk_per_trade_pct=0.75,
        base_currency="USD",
        updated_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    result = repo.get()
    assert result is not None
    assert result.account_size == 100000.0
    assert result.base_currency == "USD"


# ── S2: get_or_default() empty → default dict, no INSERT ─────────────────────


def test_s2_get_or_default_empty_returns_defaults(db: Session, repo: UserSettingsRepository) -> None:
    result = repo.get_or_default()
    assert result["account_size"] == 100000.0
    assert result["max_exposure_pct"] == 80.0
    assert result["single_trade_risk_pct"] == 1.0
    assert result["default_risk_per_trade_pct"] == 0.75
    assert result["base_currency"] == "USD"
    assert result["updated_at"] is None

    # Must NOT write to DB
    count = db.execute(text("SELECT COUNT(*) FROM user_settings")).scalar()
    assert count == 0


# ── S3: get_or_default() with existing row ────────────────────────────────────


def test_s3_get_or_default_with_row(db: Session, repo: UserSettingsRepository) -> None:
    now = datetime.now(timezone.utc)
    row = UserSettings(
        id=1,
        account_size=200000.0,
        max_exposure_pct=60.0,
        single_trade_risk_pct=0.5,
        default_risk_per_trade_pct=0.5,
        base_currency="USD",
        updated_at=now,
    )
    db.add(row)
    db.commit()

    result = repo.get_or_default()
    assert result["account_size"] == 200000.0
    assert result["max_exposure_pct"] == 60.0
    assert result["updated_at"] is not None


# ── S4: upsert() on empty table → creates id=1 row ───────────────────────────


def test_s4_upsert_creates_row_when_empty(repo: UserSettingsRepository) -> None:
    row = repo.upsert({"account_size": 200000.0})
    assert row.id == 1
    assert row.account_size == 200000.0
    # other fields retain defaults
    assert row.max_exposure_pct == 80.0
    assert row.single_trade_risk_pct == 1.0
    assert row.default_risk_per_trade_pct == 0.75
    assert row.base_currency == "USD"
    assert row.updated_at is not None


# ── S5: upsert() partial update on existing row ───────────────────────────────


def test_s5_upsert_partial_update_preserves_other_fields(
    db: Session, repo: UserSettingsRepository
) -> None:
    original_time = datetime(2026, 1, 1, 0, 0, 0)
    row = UserSettings(
        id=1,
        account_size=100000.0,
        max_exposure_pct=80.0,
        single_trade_risk_pct=1.0,
        default_risk_per_trade_pct=0.75,
        base_currency="USD",
        updated_at=original_time,
    )
    db.add(row)
    db.commit()

    time.sleep(0.01)  # ensure updated_at advances
    updated = repo.upsert({"single_trade_risk_pct": 0.5})

    assert updated.single_trade_risk_pct == 0.5
    assert updated.account_size == 100000.0       # unchanged
    assert updated.max_exposure_pct == 80.0        # unchanged
    assert updated.updated_at > original_time      # advanced


# ── S6: upsert({}) → no error ─────────────────────────────────────────────────


def test_s6_upsert_empty_patch_no_error_existing_row(
    db: Session, repo: UserSettingsRepository
) -> None:
    original_time = datetime(2026, 1, 1, 0, 0, 0)
    row = UserSettings(
        id=1,
        account_size=100000.0,
        max_exposure_pct=80.0,
        single_trade_risk_pct=1.0,
        default_risk_per_trade_pct=0.75,
        base_currency="USD",
        updated_at=original_time,
    )
    db.add(row)
    db.commit()

    time.sleep(0.01)
    result = repo.upsert({})
    assert result.id == 1
    assert result.updated_at > original_time


def test_s6_upsert_empty_patch_no_error_empty_table(repo: UserSettingsRepository) -> None:
    result = repo.upsert({})
    assert result.id == 1
    assert result.updated_at is not None


# ── S8–S12: Integration tests (FastAPI TestClient) ───────────────────────────
# Uses conftest `client` (StaticPool, Base.metadata.create_all) and `db_session`.


def test_s8_get_empty_table_returns_defaults(client: TestClient, db_session: Session) -> None:
    resp = client.get("/api/cockpit/user-settings")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["accountSize"] == 100000.0
    assert data["maxExposurePct"] == 80.0
    assert data["singleTradeRiskPct"] == 1.0
    assert data["defaultRiskPerTradePct"] == 0.75
    assert data["baseCurrency"] == "USD"
    assert data["updatedAt"] is None

    # table must still be empty
    count = db_session.execute(text("SELECT COUNT(*) FROM user_settings")).scalar()
    assert count == 0


def test_s9_get_with_row_returns_camel_keys(client: TestClient) -> None:
    # seed a row via PUT
    client.put("/api/cockpit/user-settings", json={"accountSize": 150000.0})
    resp = client.get("/api/cockpit/user-settings")
    assert resp.status_code == 200
    data = resp.json()["data"]
    # all camelCase keys present
    for key in ("accountSize", "maxExposurePct", "singleTradeRiskPct",
                "defaultRiskPerTradePct", "baseCurrency", "updatedAt"):
        assert key in data, f"Missing key: {key}"
    assert data["accountSize"] == 150000.0
    assert data["updatedAt"] is not None


def test_s10_put_partial_update(client: TestClient) -> None:
    resp = client.put(
        "/api/cockpit/user-settings",
        json={"accountSize": 150000, "singleTradeRiskPct": 0.75},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["accountSize"] == 150000.0
    assert data["singleTradeRiskPct"] == 0.75
    assert data["defaultRiskPerTradePct"] == 0.75  # unchanged default


@pytest.mark.parametrize("body", [
    {"accountSize": 0},
    {"accountSize": -1},
    {"maxExposurePct": 101},
    {"maxExposurePct": -0.1},
    {"singleTradeRiskPct": 5.1},
    {"singleTradeRiskPct": -0.5},
])
def test_s11_put_validation_422(client: TestClient, body: dict) -> None:
    resp = client.put("/api/cockpit/user-settings", json=body)
    assert resp.status_code == 422, f"Expected 422 for body={body}, got {resp.status_code}"


def test_s12_put_then_get_consistent(client: TestClient) -> None:
    put_resp = client.put(
        "/api/cockpit/user-settings",
        json={"accountSize": 250000.0, "baseCurrency": "HKD"},
    )
    assert put_resp.status_code == 200
    put_data = put_resp.json()["data"]

    get_resp = client.get("/api/cockpit/user-settings")
    assert get_resp.status_code == 200
    get_data = get_resp.json()["data"]

    assert get_data["accountSize"] == put_data["accountSize"]
    assert get_data["baseCurrency"] == put_data["baseCurrency"]
    assert get_data["updatedAt"] == put_data["updatedAt"]
