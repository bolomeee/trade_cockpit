"""F217-b1: integration tests for setup_snapshots.legacy column + PULLBACK soft-delete.

Tests T1-T9 (T10 = full regression, run separately as Step 6).

T1  alembic 021 upgrade/downgrade/upgrade roundtrip — column appears and disappears
T2  upgrade 021 soft-deletes pre-existing PULLBACK rows, leaves others untouched
T3  purge_legacy_pullback() is idempotent (rowcount first=N, second=0)
T4  purge_legacy_pullback() doesn't mark non-PULLBACK rows as legacy
T5  get_latest_all_active: latest-row legacy=True → returns [] (no fallback to next row)
T6  get_latest_for_tickers delegates to get_latest_all_active (same behavior)
T7  decision_service: only-legacy-rows → LookupError; legacy+non-legacy → returns non-legacy row
T8  upsert_batch: new row → legacy=False; on-conflict → legacy value preserved
T9  delete_before does not discriminate by legacy value
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.models.setup_snapshot import SetupSnapshot
from app.repositories.setup_snapshot_repository import SetupSnapshotRepository
from app.services.cockpit.decision_service import compute_decision

# ─── Alembic helpers ──────────────────────────────────────────────────────────


def _alembic_cfg(db_path: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


# ─── ORM-session helpers ──────────────────────────────────────────────────────


def _make_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )


def _snap(
    ticker: str,
    scan_date: date,
    setup_type: str = "BREAKOUT",
    legacy: bool = False,
    entry_price: float = 100.0,
    stop_price: float = 90.0,
    **kwargs,
) -> SetupSnapshot:
    return SetupSnapshot(
        ticker=ticker,
        scan_date=scan_date,
        setup_type=setup_type,
        earnings_risk="SAFE",
        ready_signal=True,
        legacy=legacy,
        entry_price=entry_price,
        stop_price=stop_price,
        target_2r=entry_price + 2 * (entry_price - stop_price),
        target_3r=entry_price + 3 * (entry_price - stop_price),
        reward_risk=2.0,
        scanned_at=datetime.now(timezone.utc),
        **kwargs,
    )


@pytest.fixture
def db() -> Session:
    engine = _make_engine()
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


# ─── T1: alembic migration roundtrip ─────────────────────────────────────────


def test_T1_migration_upgrade_downgrade_upgrade(tmp_path):
    db_path = str(tmp_path / "migration_test.db")
    cfg = _alembic_cfg(db_path)

    command.upgrade(cfg, "head")
    conn = sqlite3.connect(db_path)
    cols = {c[1]: c for c in conn.execute("PRAGMA table_info(setup_snapshots)").fetchall()}
    assert "legacy" in cols, "legacy column must exist after upgrade"
    assert cols["legacy"][3] == 1, "legacy must be NOT NULL"
    conn.close()

    # `legacy` is added by migration 021; downgrade to its down_revision (020)
    # so 021.down() runs and drops it (head has since advanced past 021, so a
    # bare "-1" would only reverse the newest migration and leave legacy intact).
    command.downgrade(cfg, "020_f216d1_setup_weekly_stage_column")
    conn = sqlite3.connect(db_path)
    cols_after_down = {c[1] for c in conn.execute("PRAGMA table_info(setup_snapshots)").fetchall()}
    assert "legacy" not in cols_after_down, "legacy column must disappear after downgrade"
    conn.close()

    command.upgrade(cfg, "head")
    conn = sqlite3.connect(db_path)
    cols_final = {c[1] for c in conn.execute("PRAGMA table_info(setup_snapshots)").fetchall()}
    assert "legacy" in cols_final, "legacy column must reappear after second upgrade"
    conn.close()


# ─── T2: upgrade soft-deletes pre-existing PULLBACK rows ─────────────────────


def test_T2_upgrade_soft_deletes_pullback_rows(tmp_path):
    db_path = str(tmp_path / "t2_test.db")
    cfg = _alembic_cfg(db_path)

    # Bring schema to 020 (one step before 021)
    command.upgrade(cfg, "020_f216d1_setup_weekly_stage_column")

    conn = sqlite3.connect(db_path)
    today = "2026-01-01"
    base = ("ticker", "scan_date", "setup_type", "earnings_risk", "ready_signal", "scanned_at")
    for ticker, setup_type in [("PULL", "PULLBACK"), ("BRKT", "BREAKOUT"), ("NONE", "NONE")]:
        conn.execute(
            f"INSERT INTO setup_snapshots ({', '.join(base)}) VALUES (?,?,?,?,?,?)",
            (ticker, today, setup_type, "SAFE", 1, "2026-01-01T00:00:00"),
        )
    conn.commit()
    conn.close()

    command.upgrade(cfg, "021_f217b1_setup_snapshots_legacy")

    conn = sqlite3.connect(db_path)
    rows = {
        r[0]: r[1]
        for r in conn.execute("SELECT ticker, legacy FROM setup_snapshots").fetchall()
    }
    conn.close()

    assert rows["PULL"] == 1, "PULLBACK row must be soft-deleted (legacy=1)"
    assert rows["BRKT"] == 0, "BREAKOUT row must remain active (legacy=0)"
    assert rows["NONE"] == 0, "NONE row must remain active (legacy=0)"


# ─── T3: purge_legacy_pullback idempotency ────────────────────────────────────


def test_T3_purge_idempotent(db):
    repo = SetupSnapshotRepository(db)
    d = date(2026, 1, 1)
    db.add(_snap("PULL1", d, setup_type="PULLBACK", legacy=False))
    db.add(_snap("PULL2", d, setup_type="PULLBACK", legacy=False))
    db.add(_snap("BRKT", d, setup_type="BREAKOUT", legacy=False))
    db.flush()

    first = repo.purge_legacy_pullback()
    assert first == 2, f"expected 2 PULLBACK rows purged, got {first}"

    second = repo.purge_legacy_pullback()
    assert second == 0, "second call must be idempotent (rowcount=0)"


# ─── T4: purge does not affect non-PULLBACK rows ─────────────────────────────


def test_T4_purge_only_marks_pullback(db):
    repo = SetupSnapshotRepository(db)
    d = date(2026, 1, 1)
    for setup_type in ("BREAKOUT", "NONE", "CAPITULATION", "RECLAIM"):
        db.add(_snap(setup_type, d, setup_type=setup_type, legacy=False))
    db.add(_snap("PULL", d, setup_type="PULLBACK", legacy=False))
    db.flush()

    repo.purge_legacy_pullback()

    for setup_type in ("BREAKOUT", "NONE", "CAPITULATION", "RECLAIM"):
        snap = db.execute(
            select(SetupSnapshot).where(SetupSnapshot.ticker == setup_type)
        ).scalar_one()
        assert snap.legacy is False, f"{setup_type} must not be marked legacy by purge"

    pull = db.execute(
        select(SetupSnapshot).where(SetupSnapshot.ticker == "PULL")
    ).scalar_one()
    assert pull.legacy is True


# ─── T5: get_latest_all_active: legacy=True latest → returns [] ──────────────


def test_T5_get_latest_all_active_excludes_legacy_row(db):
    repo = SetupSnapshotRepository(db)
    # Only row for ticker X is legacy=True — must not appear in results
    db.add(_snap("X", date(2026, 1, 10), setup_type="BREAKOUT", legacy=True))
    db.flush()

    result = repo.get_latest_all_active(["X"])
    assert result == [], "legacy=True row must be completely invisible (no fallback)"


def test_T5b_get_latest_all_active_returns_non_legacy_when_newer_is_legacy(db):
    """Variant: legacy=True is the newest row; older legacy=False row must NOT be returned
    by get_latest_all_active (because active_tickers logic filters per-ticker, returning
    only the single newest non-legacy row — and 'newest non-legacy' is the older row here).

    The key: legacy=True row is NOT the fallback; the non-legacy older row IS returned.
    """
    repo = SetupSnapshotRepository(db)
    db.add(_snap("Y", date(2026, 1, 10), setup_type="PULLBACK", legacy=True))
    db.add(_snap("Y", date(2026, 1, 5), setup_type="BREAKOUT", legacy=False))
    db.flush()

    result = repo.get_latest_all_active(["Y"])
    assert len(result) == 1
    assert result[0].scan_date == date(2026, 1, 5), "must return the older non-legacy row"
    assert result[0].setup_type == "BREAKOUT"


# ─── T6: get_latest_for_tickers delegates to get_latest_all_active ───────────


def test_T6_get_latest_for_tickers_consistent_with_get_latest_all_active(db):
    repo = SetupSnapshotRepository(db)
    db.add(_snap("Z", date(2026, 1, 10), setup_type="BREAKOUT", legacy=True))
    db.add(_snap("Z", date(2026, 1, 5), setup_type="NONE", legacy=False))
    db.flush()

    via_all_active = repo.get_latest_all_active(["Z"])
    via_for_tickers = repo.get_latest_for_tickers(["Z"])

    assert len(via_all_active) == len(via_for_tickers)
    if via_all_active:
        assert via_all_active[0].id == via_for_tickers[0].id


# ─── T7: decision_service legacy filtering ────────────────────────────────────


def test_T7a_decision_service_raises_lookup_when_only_legacy_rows(db):
    """Only legacy=True rows exist → compute_decision raises LookupError (no entry/stop)."""
    db.add(_snap("LEGONLY", date(2026, 1, 10), setup_type="PULLBACK", legacy=True))
    db.flush()

    with pytest.raises(LookupError):
        compute_decision(db, "LEGONLY")


def test_T7b_decision_service_returns_older_non_legacy_row(db):
    """legacy=True newest row + legacy=False older row → service uses the older non-legacy row."""
    db.add(
        _snap("MIX", date(2026, 1, 10), setup_type="PULLBACK", legacy=True,
              entry_price=200.0, stop_price=180.0)
    )
    db.add(
        _snap("MIX", date(2026, 1, 5), setup_type="BREAKOUT", legacy=False,
              entry_price=100.0, stop_price=90.0)
    )
    db.flush()

    result = compute_decision(db, "MIX")

    assert result.setup_type == "BREAKOUT", "must use the non-legacy row (older)"
    assert result.entry_price == 100.0
    assert result.stop_price == 90.0


# ─── T8: upsert_batch legacy behavior ────────────────────────────────────────


def test_T8a_upsert_batch_new_row_has_legacy_false(db):
    """New row inserted via upsert_batch (no legacy key in dict) → legacy=False (ORM default)."""
    repo = SetupSnapshotRepository(db)
    row = {
        "ticker": "NEW",
        "scan_date": date(2026, 1, 1),
        "setup_type": "BREAKOUT",
        "earnings_risk": "SAFE",
        "ready_signal": True,
        "scanned_at": datetime.now(timezone.utc),
    }
    repo.upsert_batch([row])

    snap = db.execute(select(SetupSnapshot).where(SetupSnapshot.ticker == "NEW")).scalar_one()
    assert snap.legacy is False, "new upsert_batch row must have legacy=False"


def test_T8b_upsert_batch_conflict_does_not_overwrite_legacy(db):
    """On-conflict update (same ticker+scan_date) must not change the existing legacy value."""
    repo = SetupSnapshotRepository(db)
    d = date(2026, 1, 1)
    # Insert row, then manually mark legacy=True
    repo.upsert_batch([{
        "ticker": "KEEP", "scan_date": d, "setup_type": "PULLBACK",
        "earnings_risk": "SAFE", "ready_signal": True,
        "scanned_at": datetime.now(timezone.utc),
    }])
    snap = db.execute(select(SetupSnapshot).where(SetupSnapshot.ticker == "KEEP")).scalar_one()
    snap.legacy = True
    db.commit()

    # On-conflict update — same (ticker, scan_date), no legacy key in row dict
    repo.upsert_batch([{
        "ticker": "KEEP", "scan_date": d, "setup_type": "NONE",
        "earnings_risk": "SAFE", "ready_signal": False,
        "scanned_at": datetime.now(timezone.utc),
    }])

    db.expire_all()
    updated = db.execute(select(SetupSnapshot).where(SetupSnapshot.ticker == "KEEP")).scalar_one()
    assert updated.setup_type == "NONE", "setup_type should be updated"
    assert updated.legacy is True, "legacy must not be overwritten by on-conflict update"


# ─── T9: delete_before ignores legacy status ─────────────────────────────────


def test_T9_delete_before_removes_regardless_of_legacy(db):
    repo = SetupSnapshotRepository(db)
    cutoff = date(2026, 1, 10)
    db.add(_snap("A", date(2026, 1, 5), legacy=False))   # before cutoff, non-legacy
    db.add(_snap("B", date(2026, 1, 5), legacy=True))    # before cutoff, legacy
    db.add(_snap("C", date(2026, 1, 15), legacy=False))  # after cutoff, non-legacy
    db.add(_snap("D", date(2026, 1, 15), legacy=True))   # after cutoff, legacy
    db.flush()

    deleted = repo.delete_before(cutoff)
    assert deleted == 2, "must delete both rows before cutoff regardless of legacy"

    remaining = db.execute(select(SetupSnapshot)).scalars().all()
    tickers = {s.ticker for s in remaining}
    assert tickers == {"C", "D"}, "rows after cutoff must survive regardless of legacy"
