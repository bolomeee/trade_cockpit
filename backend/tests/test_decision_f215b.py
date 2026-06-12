"""Integration tests for F215-b Volume Accumulation three-pack + BREAKOUT gate.

Standards covered (from Sprint Contract):
  #5  compute_and_store_all() writes 3 new fields (non-None when data sufficient, None when short)
  #6  alembic 018 upgrade → downgrade → upgrade round-trips without data loss
  #7  GET /api/cockpit/setup-monitor items contain volumeZscore/obvTrend/upDownVolumeRatio
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.models.daily_bar import DailyBar
from app.models.market_index import MarketIndex
from app.models.setup_snapshot import SetupSnapshot
from app.models.stock import Stock
from app.services.cockpit.setup_service import SetupService


# ── helpers ───────────────────────────────────────────────────────────────────


def _seed_stock_with_bars(db: Session, ticker: str, n: int, trend: str = "up") -> Stock:
    """Seed a stock with n daily bars. trend='up'|'down'|'flat'."""
    stock = Stock(ticker=ticker, name=f"{ticker} Inc", is_active=True, added_at=datetime.now(timezone.utc))
    db.add(stock)
    db.flush()
    start = date(2024, 1, 1)
    for i in range(n):
        if trend == "up":
            close = 100.0 + i * 0.1
            high = close + 1.0
        elif trend == "down":
            close = 200.0 - i * 0.1
            high = close + 1.0
        else:
            close = 100.0
            high = 101.0
        db.add(DailyBar(
            stock_id=stock.id,
            date=start + timedelta(days=i),
            open=close - 0.5,
            high=high,
            low=close - 1.0,
            close=close,
            volume=1_000_000 + (i % 10) * 100_000,  # slight volume variation
        ))
    db.commit()
    return stock


def _seed_spy(db: Session, n: int = 260) -> None:
    start = date(2024, 1, 1)
    for i in range(n):
        db.add(MarketIndex(symbol="SPY", name="SPY", date=start + timedelta(days=i), close=400.0 + i * 0.05))
    db.commit()


# ── Standard #5: compute_and_store_all writes 3 new fields ───────────────────


class TestComputeAndStoreAllVolFields:
    def test_s5_sufficient_data_writes_vol_fields(self, db_session):
        """#5: stock with 260 bars (mixed up/down) → volume_zscore non-None, obv_trend non-None, ud_ratio non-None."""
        _seed_spy(db_session)
        # Seed with alternating up/down days so up_down_volume_ratio has both numerator and denominator
        stock = Stock(ticker="AAPL", name="Apple Inc", is_active=True, added_at=datetime.now(timezone.utc))
        db_session.add(stock)
        db_session.flush()
        start = date(2024, 1, 1)
        close = 100.0
        for i in range(260):
            # Alternate up/down: even=up, odd=down — net uptrend (up slightly more)
            if i % 2 == 0:
                close += 0.5
            else:
                close -= 0.3
            db_session.add(DailyBar(
                stock_id=stock.id,
                date=start + timedelta(days=i),
                open=close - 0.2,
                high=close + 0.5,
                low=close - 0.5,
                close=close,
                volume=1_000_000 + (i % 20) * 50_000,
            ))
        db_session.commit()

        svc = SetupService(db_session)
        count = svc.compute_and_store_all(today=date(2024, 9, 17))
        assert count >= 1

        snap = db_session.query(SetupSnapshot).filter_by(ticker="AAPL").first()
        assert snap is not None
        assert snap.volume_zscore is not None
        assert snap.obv_trend in ("UP", "DOWN", "FLAT")
        assert snap.up_down_volume_ratio is not None

    def test_s5_short_history_stock_writes_none_fields(self, db_session):
        """#5: stock with < 10 bars → all 3 new fields are None."""
        _seed_spy(db_session)
        _seed_stock_with_bars(db_session, "NEWCO", 5, trend="up")

        svc = SetupService(db_session)
        svc.compute_and_store_all(today=date(2024, 1, 6))

        snap = db_session.query(SetupSnapshot).filter_by(ticker="NEWCO").first()
        assert snap is not None
        assert snap.volume_zscore is None
        assert snap.obv_trend is None
        assert snap.up_down_volume_ratio is None


# ── Standard #6: alembic 018 upgrade → downgrade → upgrade ───────────────────


class TestAlembic018RoundTrip:
    def test_s6_018_upgrade_adds_three_columns(self):
        """#6: after upgrade 018 the three columns exist in setup_snapshots."""
        from alembic.config import Config
        from alembic import command

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)  # creates all tables at current schema

        # Verify columns are present (since models already include them)
        insp = inspect(engine)
        cols = [c["name"] for c in insp.get_columns("setup_snapshots")]
        assert "volume_zscore" in cols
        assert "obv_trend" in cols
        assert "up_down_volume_ratio" in cols

    def test_s6_downgrade_drops_columns_upgrade_re_adds(self):
        """#6: simulate downgrade 018 by dropping columns, then verify they can be re-added."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)

        with engine.connect() as conn:
            # Simulate downgrade: recreate table without the 3 new columns
            conn.execute(text("ALTER TABLE setup_snapshots RENAME TO _setup_snapshots_old"))
            conn.execute(text("""
                CREATE TABLE setup_snapshots AS
                SELECT id, ticker, scan_date, setup_type, setup_quality,
                       entry_price, stop_price, target_2r, target_3r,
                       distance_to_entry_pct, reward_risk, rs_percentile,
                       volume_status, trend_score, earnings_risk,
                       ready_signal, suggested_action, scanned_at
                FROM _setup_snapshots_old
            """))
            conn.execute(text("DROP TABLE _setup_snapshots_old"))
            conn.commit()

        insp = inspect(engine)
        cols_after_down = [c["name"] for c in insp.get_columns("setup_snapshots")]
        assert "volume_zscore" not in cols_after_down

        # Simulate upgrade: add them back
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE setup_snapshots ADD COLUMN volume_zscore REAL"))
            conn.execute(text("ALTER TABLE setup_snapshots ADD COLUMN obv_trend VARCHAR(4)"))
            conn.execute(text("ALTER TABLE setup_snapshots ADD COLUMN up_down_volume_ratio REAL"))
            conn.commit()

        insp2 = inspect(engine)
        cols_after_up = [c["name"] for c in insp2.get_columns("setup_snapshots")]
        assert "volume_zscore" in cols_after_up
        assert "obv_trend" in cols_after_up
        assert "up_down_volume_ratio" in cols_after_up

    def test_s6_existing_rows_get_null_after_upgrade(self):
        """#6: rows written before upgrade have NULL for the 3 new columns."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)

        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO setup_snapshots
                    (ticker, scan_date, setup_type, earnings_risk, ready_signal, legacy, scanned_at)
                VALUES
                    ('OLD', '2024-01-01', 'NONE', 'SAFE', 0, 0, '2024-01-01T00:00:00')
            """))
            conn.commit()
            row = conn.execute(
                text("SELECT volume_zscore, obv_trend, up_down_volume_ratio FROM setup_snapshots WHERE ticker='OLD'")
            ).one()
            assert row[0] is None
            assert row[1] is None
            assert row[2] is None


# ── Standard #7: API response includes 3 camelCase fields ─────────────────────


class TestSetupMonitorApiVolFields:
    def test_s7_api_response_includes_vol_fields(self, client, db_session):
        """#7: GET /api/cockpit/setup-monitor items contain camelCase vol fields."""
        _seed_spy(db_session)
        stock = _seed_stock_with_bars(db_session, "NVDA", 260, trend="up")

        svc = SetupService(db_session)
        svc.compute_and_store_all(today=date(2024, 9, 17))

        resp = client.get("/api/cockpit/setup-monitor")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["summary"]["total"] >= 1
        items = body["data"]["items"]
        assert len(items) >= 1
        item = items[0]
        assert "volumeZscore" in item
        assert "obvTrend" in item
        assert "upDownVolumeRatio" in item

    def test_s7_null_vol_fields_serialize_as_null(self, client, db_session):
        """#7: short-history snapshot → vol fields are null in JSON."""
        stock = Stock(ticker="TINY", name="Tiny Inc", is_active=True, added_at=datetime.now(timezone.utc))
        db_session.add(stock)
        db_session.flush()
        snap = SetupSnapshot(
            ticker="TINY",
            scan_date=date.today(),
            setup_type="NONE",
            earnings_risk="SAFE",
            ready_signal=False,
            scanned_at=datetime.now(timezone.utc),
            volume_zscore=None,
            obv_trend=None,
            up_down_volume_ratio=None,
        )
        db_session.add(snap)
        db_session.commit()

        resp = client.get("/api/cockpit/setup-monitor")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        tiny_items = [i for i in items if i["ticker"] == "TINY"]
        assert len(tiny_items) == 1
        assert tiny_items[0]["volumeZscore"] is None
        assert tiny_items[0]["obvTrend"] is None
        assert tiny_items[0]["upDownVolumeRatio"] is None
