"""F218-d1 skeleton tests — RepricingTrigger (repo CRUD + service end-to-end + migration + constants).

14 tests grouped into 4 classes:
  TestRepricingTriggerRepository  — R1–R8  (repo CRUD + UQ)
  TestRepricingTriggerServiceSkeleton — S9–S12 (service e2e + DetectorResult)
  TestRepricingTriggerMigration   — M13     (alembic 022 upgrade/downgrade/re-upgrade)
  TestRepricingTriggerConstants   — C14     (TRIGGER_TYPES literal)
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import RepricingTrigger, Stock
from app.repositories.repricing_trigger_repository import RepricingTriggerRepository
from app.services.cockpit.repricing_trigger_service import (
    TRIGGER_TYPES,
    DetectorResult,
    RepricingTriggerService,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _trigger(
    db: Session,
    *,
    ticker: str = "AAPL",
    trigger_type: str = "EARNINGS_ACCEL",
    detected_date: date = date(2026, 1, 1),
    confidence: float = 0.8,
    active: bool = True,
) -> RepricingTrigger:
    row = RepricingTrigger(
        ticker=ticker,
        trigger_type=trigger_type,
        detected_date=detected_date,
        confidence=confidence,
        evidence_json=json.dumps({"test": True}),
        active=active,
        computed_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _stock(db: Session, ticker: str = "AAPL") -> Stock:
    row = Stock(
        ticker=ticker,
        name=f"{ticker} Inc",
        exchange="NASDAQ",
        is_active=True,
        added_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ── Class 1: Repository CRUD ──────────────────────────────────────────────────


class TestRepricingTriggerRepository:

    def test_r1_upsert_insert_new_row(self, db_session: Session) -> None:
        repo = RepricingTriggerRepository(db_session)
        row = repo.upsert({
            "ticker": "AAPL",
            "trigger_type": "EARNINGS_ACCEL",
            "detected_date": date(2026, 5, 1),
            "confidence": 0.9,
            "evidence_json": json.dumps({"eps_growth": 0.35}),
            "active": True,
            "computed_at": datetime.now(timezone.utc),
        })
        assert row.id is not None
        assert row.ticker == "AAPL"
        assert row.active is True
        assert row.confidence == pytest.approx(0.9)

    def test_r2_upsert_on_conflict_updates_existing(self, db_session: Session) -> None:
        repo = RepricingTriggerRepository(db_session)
        base = {
            "ticker": "AAPL",
            "trigger_type": "EARNINGS_ACCEL",
            "detected_date": date(2026, 5, 1),
            "confidence": 0.7,
            "evidence_json": json.dumps({"v": 1}),
            "active": True,
            "computed_at": datetime.now(timezone.utc),
        }
        r1 = repo.upsert(base)
        original_id = r1.id

        r2 = repo.upsert({**base, "confidence": 0.95, "evidence_json": json.dumps({"v": 2})})

        assert r2.id == original_id, "ON CONFLICT must not create new row"
        assert r2.confidence == pytest.approx(0.95)
        assert r2.evidence_json == json.dumps({"v": 2})
        total = db_session.execute(
            select(func.count()).select_from(RepricingTrigger)
        ).scalar_one()
        assert total == 1

    def test_r3_soft_expire_marks_old_active_rows_inactive(self, db_session: Session) -> None:
        repo = RepricingTriggerRepository(db_session)
        today = date(2026, 5, 18)
        _trigger(db_session, detected_date=date(2026, 5, 10), active=True)
        _trigger(db_session, detected_date=date(2026, 4, 1), active=False)  # already inactive

        updated = repo.soft_expire("AAPL", "EARNINGS_ACCEL", today)
        assert updated == 1  # only the active row flips

        rows = db_session.execute(select(RepricingTrigger)).scalars().all()
        assert all(r.active is False for r in rows)

    def test_r4_get_active_for_ticker(self, db_session: Session) -> None:
        repo = RepricingTriggerRepository(db_session)
        _trigger(db_session, ticker="AAPL", detected_date=date(2026, 5, 1), active=True)
        _trigger(db_session, ticker="AAPL", detected_date=date(2026, 4, 1), active=False)
        _trigger(db_session, ticker="MSFT", detected_date=date(2026, 5, 1), active=True)

        rows = repo.get_active_for_ticker("AAPL")
        assert len(rows) == 1
        assert rows[0].ticker == "AAPL"
        assert rows[0].active is True
        # no-match case returns empty list, not 404
        assert repo.get_active_for_ticker("UNKNOWN") == []

    def test_r5_get_all_active_no_filter(self, db_session: Session) -> None:
        repo = RepricingTriggerRepository(db_session)
        _trigger(db_session, ticker="AAPL", trigger_type="EARNINGS_ACCEL", active=True)
        _trigger(db_session, ticker="MSFT", trigger_type="SECTOR_CYCLE", active=True)
        _trigger(db_session, ticker="TSLA", trigger_type="NEW_PRODUCT", active=False)

        rows, total = repo.get_all_active()
        assert total == 2
        assert len(rows) == 2
        assert all(r.active is True for r in rows)

    def test_r6_get_all_active_with_type_filter(self, db_session: Session) -> None:
        repo = RepricingTriggerRepository(db_session)
        _trigger(db_session, ticker="AAPL", trigger_type="MARGIN_EXPANSION", active=True)
        _trigger(db_session, ticker="MSFT", trigger_type="EARNINGS_ACCEL", active=True)

        rows, total = repo.get_all_active(trigger_type="MARGIN_EXPANSION")
        assert total == 1
        assert rows[0].trigger_type == "MARGIN_EXPANSION"

    def test_r7_delete_expired_inactive_respects_boundaries(self, db_session: Session) -> None:
        repo = RepricingTriggerRepository(db_session)
        cutoff = date(2026, 1, 1)
        _trigger(db_session, detected_date=date(2025, 12, 31), active=False)                         # delete
        _trigger(db_session, detected_date=date(2026, 1, 1), active=False, trigger_type="SECTOR_CYCLE")   # on cutoff → keep
        _trigger(db_session, detected_date=date(2025, 12, 31), active=True, trigger_type="NEW_PRODUCT")   # active → keep

        deleted = repo.delete_expired_inactive(cutoff)
        assert deleted == 1

        remaining = db_session.execute(select(RepricingTrigger)).scalars().all()
        assert len(remaining) == 2
        for r in remaining:
            assert not (r.active is False and r.detected_date < cutoff)

    def test_r8_upsert_uq_three_times_id_stable(self, db_session: Session) -> None:
        """ON CONFLICT path does not raise; id is stable across 3 consecutive upserts."""
        repo = RepricingTriggerRepository(db_session)
        base = {
            "ticker": "TSLA",
            "trigger_type": "BALANCE_INFLECTION",
            "detected_date": date(2026, 3, 1),
            "confidence": 0.6,
            "evidence_json": json.dumps({"x": 0}),
            "active": True,
            "computed_at": datetime.now(timezone.utc),
        }
        r1 = repo.upsert(base)
        r2 = repo.upsert({**base, "confidence": 0.7})
        r3 = repo.upsert({**base, "confidence": 0.8})

        assert r1.id == r2.id == r3.id
        assert r3.confidence == pytest.approx(0.8)


# ── Class 2: Service Skeleton ─────────────────────────────────────────────────


class TestRepricingTriggerServiceSkeleton:

    def test_s9_all_none_no_existing_rows_returns_zero_counts(
        self, db_session: Session
    ) -> None:
        _stock(db_session, "AAPL")
        svc = RepricingTriggerService(db_session)
        counts = svc.compute_and_store_all_triggers(scan_date=date(2026, 5, 18))

        assert counts == {t: 0 for t in TRIGGER_TYPES}
        rows = db_session.execute(select(RepricingTrigger)).scalars().all()
        assert rows == []

    def test_s10_all_none_with_existing_active_soft_expires(
        self, db_session: Session
    ) -> None:
        _stock(db_session, "AAPL")
        scan_date = date(2026, 5, 18)
        _trigger(
            db_session,
            ticker="AAPL",
            trigger_type="EARNINGS_ACCEL",
            detected_date=date(2026, 5, 10),
            active=True,
        )

        svc = RepricingTriggerService(db_session)
        svc.compute_and_store_all_triggers(scan_date=scan_date)

        row = db_session.execute(select(RepricingTrigger)).scalar_one()
        assert row.active is False

    def test_s11_detector_exception_isolated_loop_continues(
        self, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stock(db_session, "AAPL")
        svc = RepricingTriggerService(db_session)

        def _raise(*_: object) -> None:
            raise RuntimeError("simulated detector failure")

        monkeypatch.setattr(svc, "_detect_earnings_acceleration", _raise)
        # Must not propagate — exception is caught by logger.exception + continue
        counts = svc.compute_and_store_all_triggers(scan_date=date(2026, 5, 18))
        assert counts["EARNINGS_ACCEL"] == 0
        assert counts["SECTOR_CYCLE"] == 0

    def test_s12_detector_result_serializes_to_evidence_json(self) -> None:
        evidence = {"eps_growth": 0.35, "quarters": [1.1, 1.2, 1.3, 1.4]}
        result = DetectorResult(confidence=0.85, evidence=evidence)
        roundtrip = json.loads(json.dumps(result.evidence))
        assert roundtrip["eps_growth"] == pytest.approx(0.35)
        assert roundtrip["quarters"] == evidence["quarters"]
        assert result.confidence == pytest.approx(0.85)


# ── Class 3: Migration ────────────────────────────────────────────────────────


class TestRepricingTriggerMigration:

    def test_m13_alembic_022_upgrade_downgrade_re_upgrade(self) -> None:
        from alembic import command
        from alembic.config import Config

        tmp = tempfile.mkdtemp()
        try:
            db_path = os.path.join(tmp, "test_022.db")
            ini_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
            )
            cfg = Config(ini_path)
            cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

            command.upgrade(cfg, "head")
            conn = sqlite3.connect(db_path)
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            indexes = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()}
            conn.close()

            assert "repricing_triggers" in tables
            assert "ix_repricing_triggers_ticker" in indexes
            assert "ix_repricing_triggers_detected_date" in indexes
            assert "ix_repricing_triggers_active" in indexes

            # Downgrade past 022 → table removed
            command.downgrade(cfg, "021_f217b1_setup_snapshots_legacy")
            conn = sqlite3.connect(db_path)
            tables_after = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            conn.close()
            assert "repricing_triggers" not in tables_after

            # Re-upgrade → idempotent
            command.upgrade(cfg, "head")
            conn = sqlite3.connect(db_path)
            tables_final = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            conn.close()
            assert "repricing_triggers" in tables_final

        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ── Class 4: Constants ────────────────────────────────────────────────────────


class TestRepricingTriggerConstants:

    def test_c14_trigger_types_constant_matches_data_model(self) -> None:
        expected = (
            "EARNINGS_ACCEL",
            "MARGIN_EXPANSION",
            "NEW_PRODUCT",
            "SECTOR_CYCLE",
            "BALANCE_INFLECTION",
        )
        assert TRIGGER_TYPES == expected, f"TRIGGER_TYPES mismatch: {TRIGGER_TYPES}"
        assert len(TRIGGER_TYPES) == 5
