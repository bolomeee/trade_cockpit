"""F202-a Setup Monitor data layer tests — Sprint Contract S1–S17."""
from __future__ import annotations

import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from app.models import Base
from app.models.daily_bar import DailyBar
from app.models.earnings_event import EarningsEvent
from app.models.market_index import MarketIndex
from app.models.market_regime_snapshot import MarketRegimeSnapshot
from app.models.setup_snapshot import SetupSnapshot
from app.models.stock import Stock
from app.repositories.setup_snapshot_repository import SetupSnapshotRepository
from app.services.cockpit.cockpit_params import SETUP
from app.services.cockpit.setup_service import (
    SetupService,
    _classify_setup_type,
    _compute_earnings_risk,
    _compute_mas,
    _compute_ready_signal,
    _compute_trend_score,
    _compute_volume_status,
    _percentile_rank,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

_TODAY = date(2026, 4, 25)
_START = date(2025, 1, 1)


@pytest.fixture()
def alembic_db(tmp_path: Path):
    """Fresh SQLite DB via alembic upgrade head, yields path string."""
    db_path = tmp_path / "test_setup.db"
    cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")
    return str(db_path)


@pytest.fixture()
def db(tmp_path: Path):
    """In-memory SQLite session with all tables created."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _insert_stock(db: Session, ticker: str, name: str = "Test Corp") -> Stock:
    stock = Stock(ticker=ticker, name=name, is_active=True, added_at=datetime.now(timezone.utc))
    db.add(stock)
    db.flush()
    return stock


def _insert_bars(
    db: Session,
    stock_id: int,
    closes: list[float],
    highs: list[float] | None = None,
    volumes: list[int] | None = None,
    start: date = _START,
) -> None:
    for i, close in enumerate(closes):
        high = (highs[i] if highs else close * 1.01)
        vol = (volumes[i] if volumes else 1_000_000)
        db.add(DailyBar(
            stock_id=stock_id,
            date=start + timedelta(days=i),
            open=close * 0.99,
            high=high,
            low=close * 0.98,
            close=close,
            volume=vol,
        ))
    db.flush()


def _insert_spy(db: Session, closes: list[float], start: date = _START) -> None:
    for i, close in enumerate(closes):
        db.add(MarketIndex(symbol="SPY", name="SPDR S&P 500", date=start + timedelta(days=i), close=close))
    db.flush()


def _insert_regime(db: Session, regime: str = "CONSTRUCTIVE") -> None:
    import json
    db.add(MarketRegimeSnapshot(
        date=_TODAY,
        regime=regime,
        market_score=65,
        spy_trend_score=20,
        qqq_trend_score=15,
        iwm_breadth_score=10,
        sector_participation_score=10,
        risk_appetite_score=5,
        volatility_stress_score=5,
        allowed_exposure_pct=70.0,
        single_trade_risk_pct=1.0,
        preferred_setups=json.dumps(["BREAKOUT", "PULLBACK"]),
        avoid_setups=json.dumps(["EXTENDED"]),
        computed_at=datetime.now(timezone.utc),
    ))
    db.flush()


# ── S1/S2: Alembic migration ──────────────────────────────────────────────────

def test_s1_alembic_upgrade_creates_table(alembic_db: str) -> None:
    engine = create_engine(f"sqlite:///{alembic_db}")
    insp = inspect(engine)
    assert "setup_snapshots" in insp.get_table_names()
    cols = {c["name"] for c in insp.get_columns("setup_snapshots")}
    for col in ("id", "ticker", "scan_date", "setup_type", "earnings_risk", "ready_signal"):
        assert col in cols, f"column {col} missing"
    uq_names = {c["name"] for c in insp.get_unique_constraints("setup_snapshots")}
    assert "uq_setup_snapshot_ticker_date" in uq_names


def test_s2_alembic_downgrade_drops_table(alembic_db: str) -> None:
    db_path = alembic_db
    cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.downgrade(cfg, "-1")
    engine = create_engine(f"sqlite:///{db_path}")
    assert "setup_snapshots" not in inspect(engine).get_table_names()


# ── S3/S4: Repository upsert ──────────────────────────────────────────────────

def test_s3_upsert_batch_inserts(db: Session) -> None:
    repo = SetupSnapshotRepository(db)
    row = {
        "ticker": "AAPL", "scan_date": _TODAY, "setup_type": "BREAKOUT",
        "setup_quality": "A", "entry_price": 150.0, "stop_price": 145.0,
        "target_2r": 160.0, "target_3r": 165.0, "distance_to_entry_pct": 1.5,
        "reward_risk": 2.0, "rs_percentile": 80.0, "volume_status": "HIGH",
        "trend_score": 4, "earnings_risk": "SAFE", "ready_signal": True,
        "suggested_action": "enter", "scanned_at": datetime.now(timezone.utc),
    }
    count = repo.upsert_batch([row])
    assert count == 1
    rows = db.execute(select(SetupSnapshot)).scalars().all()
    assert len(rows) == 1
    assert rows[0].ticker == "AAPL"
    assert rows[0].setup_type == "BREAKOUT"


def test_s4_upsert_batch_updates_on_conflict(db: Session) -> None:
    repo = SetupSnapshotRepository(db)
    base = {
        "ticker": "NVDA", "scan_date": _TODAY, "setup_type": "BREAKOUT",
        "setup_quality": "A", "entry_price": 500.0, "stop_price": 480.0,
        "target_2r": 540.0, "target_3r": 560.0, "distance_to_entry_pct": 1.0,
        "reward_risk": 2.0, "rs_percentile": 85.0, "volume_status": "HIGH",
        "trend_score": 5, "earnings_risk": "SAFE", "ready_signal": True,
        "suggested_action": "enter", "scanned_at": datetime.now(timezone.utc),
    }
    repo.upsert_batch([base])
    updated = {**base, "setup_type": "PULLBACK", "ready_signal": False, "suggested_action": "watch"}
    repo.upsert_batch([updated])
    rows = db.execute(select(SetupSnapshot).where(SetupSnapshot.ticker == "NVDA")).scalars().all()
    assert len(rows) == 1
    assert rows[0].setup_type == "PULLBACK"
    assert rows[0].ready_signal is False


# ── S5: delete_before ────────────────────────────────────────────────────────

def test_s5_delete_before_removes_old_rows(db: Session) -> None:
    repo = SetupSnapshotRepository(db)
    old_date = _TODAY - timedelta(days=70)
    new_date = _TODAY - timedelta(days=10)

    def _row(ticker: str, d: date) -> dict:
        return {
            "ticker": ticker, "scan_date": d, "setup_type": "NONE",
            "setup_quality": None, "entry_price": None, "stop_price": None,
            "target_2r": None, "target_3r": None, "distance_to_entry_pct": None,
            "reward_risk": None, "rs_percentile": 50.0, "volume_status": None,
            "trend_score": 0, "earnings_risk": "SAFE", "ready_signal": False,
            "suggested_action": None, "scanned_at": datetime.now(timezone.utc),
        }

    repo.upsert_batch([_row("AAPL", old_date), _row("NVDA", new_date)])
    deleted = repo.delete_before(_TODAY - timedelta(days=60))
    assert deleted == 1
    remaining = db.execute(select(SetupSnapshot)).scalars().all()
    assert len(remaining) == 1
    assert remaining[0].ticker == "NVDA"


# ── S6: get_latest_all_active ─────────────────────────────────────────────────

def test_s6_get_latest_returns_one_row_per_ticker(db: Session) -> None:
    repo = SetupSnapshotRepository(db)

    def _row(ticker: str, d: date, action: str | None = None) -> dict:
        return {
            "ticker": ticker, "scan_date": d, "setup_type": "NONE",
            "setup_quality": None, "entry_price": None, "stop_price": None,
            "target_2r": None, "target_3r": None, "distance_to_entry_pct": None,
            "reward_risk": None, "rs_percentile": 50.0, "volume_status": None,
            "trend_score": 0, "earnings_risk": "SAFE", "ready_signal": False,
            "suggested_action": action, "scanned_at": datetime.now(timezone.utc),
        }

    repo.upsert_batch([
        _row("AAPL", _TODAY - timedelta(days=2)),
        _row("AAPL", _TODAY - timedelta(days=1)),
        _row("AAPL", _TODAY, "enter"),
        _row("NVDA", _TODAY, "watch"),
    ])
    rows = repo.get_latest_all_active(["AAPL", "NVDA", "MSFT"])  # MSFT has no rows
    tickers = [r.ticker for r in rows]
    assert len(rows) == 2
    assert "MSFT" not in tickers
    aapl = next(r for r in rows if r.ticker == "AAPL")
    assert aapl.scan_date == _TODAY
    assert aapl.suggested_action == "enter"


# ── S7/S8: trend_score ───────────────────────────────────────────────────────

def test_s7_trend_score_full_ladder() -> None:
    closes = [float(i) for i in range(1, 250)]  # strictly increasing
    mas = _compute_mas(closes)
    score = _compute_trend_score(closes[-1], mas)
    assert score == 5


def test_s8_trend_score_partial_ladder_ma200_none() -> None:
    # Only 100 bars → MA200 is None
    closes = [float(i) for i in range(1, 101)]
    mas = _compute_mas(closes)
    assert mas[200] is None
    score = _compute_trend_score(closes[-1], mas)
    # close>ma10, ma10>ma21, ma21>ma50 should hold for ascending series; ma150>ma200 fails (None)
    # Exact value depends on series, but must be < 5
    assert score < 5


# ── S9: earnings_risk ────────────────────────────────────────────────────────

@pytest.mark.parametrize("days,expected", [
    (3, "DANGER"),
    (4, "CAUTION"),
    (10, "CAUTION"),
    (11, "SAFE"),
])
def test_s9_earnings_risk_parametrized(days: int, expected: str) -> None:
    class FakeEvent:
        earnings_date = _TODAY + timedelta(days=days)

    assert _compute_earnings_risk(FakeEvent(), _TODAY) == expected


def test_s9_earnings_risk_none_event() -> None:
    assert _compute_earnings_risk(None, _TODAY) == "SAFE"


# ── S10/S11: ready_signal ────────────────────────────────────────────────────

def _ready_kwargs(**overrides) -> dict:
    base = dict(
        trend_score=4,
        rs_percentile=75.0,
        setup_quality="A",
        distance_to_entry_pct=2.0,
        reward_risk=2.5,
        earnings_risk="SAFE",
        regime="CONSTRUCTIVE",
    )
    return {**base, **overrides}


def test_s10_ready_signal_all_conditions_met() -> None:
    assert _compute_ready_signal(**_ready_kwargs()) is True


@pytest.mark.parametrize("override,value", [
    ("trend_score", 3),                   # below READY_TREND_MIN=4
    ("rs_percentile", 69.0),             # below READY_RS_MIN=70
    ("setup_quality", "C"),              # below READY_QUALITY_MIN=B
    ("distance_to_entry_pct", 4.0),      # above READY_DIST_MAX_PCT=3
    ("reward_risk", 1.9),                # below READY_REWARD_RISK_MIN=2
    ("earnings_risk", "DANGER"),
    ("regime", "RISK_OFF"),
])
def test_s11_ready_signal_fails_on_each_condition(override: str, value) -> None:
    kwargs = _ready_kwargs(**{override: value})
    assert _compute_ready_signal(**kwargs) is False


# ── S12/S13/S14/S15: classify_setup_type ─────────────────────────────────────

def _make_closes(n: int, start: float = 100.0, step: float = 0.5) -> list[float]:
    return [start + i * step for i in range(n)]


def test_s12_classify_broken() -> None:
    closes = [120.0] * 200
    closes[-1] = 80.0  # close < ma150
    mas = _compute_mas(closes)
    st, entry, stop, t2r, t3r = _classify_setup_type(
        closes[-1], mas, closes, 3, False, closes[:-1]
    )
    assert st == "BROKEN"
    assert entry is None and stop is None


def test_s13_classify_extended() -> None:
    closes = [100.0] * 200
    closes[-1] = 120.0  # 20% above MA50 (threshold 15%)
    mas = _compute_mas(closes)
    st, entry, stop, t2r, t3r = _classify_setup_type(
        closes[-1], mas, closes, 3, False, closes[:-1]
    )
    assert st == "EXTENDED"
    assert entry is None


def test_s14_classify_breakout() -> None:
    # Build an ascending series so MA50 < MA150 < MA200, trend_score >= 3
    closes = _make_closes(250)
    # Set last 20 highs to create a pivot
    highs = list(closes)
    highs[-10] = closes[-1] * 1.01  # pivot20 slightly above last close
    # current close just below pivot: breakout zone
    last_close = highs[-10] * 0.98  # within 5% zone
    closes[-1] = last_close
    mas = _compute_mas(closes)
    ts = _compute_trend_score(last_close, mas)
    assert ts >= 3
    st, entry, stop, t2r, t3r = _classify_setup_type(
        last_close, mas, highs, ts, False, closes[:-1]
    )
    assert st == "BREAKOUT"
    assert entry is not None
    assert stop is not None
    assert t2r is not None
    # target_2r = entry + 2 * (entry - stop)
    assert abs(t2r - (entry + 2 * (entry - stop))) < 0.01


def test_s15_classify_pullback() -> None:
    # Fabricate MAs directly to guarantee pullback zone conditions:
    # close(194) between MA150(170) and MA50*1.03(198.8), above MA50*0.97(187.2)
    # pivot20(220) too far above close → BREAKOUT zone NOT triggered
    mas = {10: 200.0, 21: 195.0, 50: 193.0, 150: 170.0, 200: 165.0}
    last_close = 194.0
    highs = [220.0] * 50   # pivot20=220, close far below → no BREAKOUT
    prev_closes = [190.0] * 20  # no reclaim scenario
    trend_score = 4

    st, entry, stop, t2r, t3r = _classify_setup_type(
        last_close, mas, highs, trend_score, False, prev_closes
    )
    assert st == "PULLBACK"
    assert entry == mas[21]
    assert stop is not None
    expected_stop = round(entry * (1 - 0.03), 4)
    assert abs(stop - expected_stop) < 0.01


# ── S16: compute_and_store_all integration ────────────────────────────────────

def test_s16_compute_and_store_all(db: Session) -> None:
    # Insert 2 active stocks with sufficient bar history
    aapl = _insert_stock(db, "AAPL")
    nvda = _insert_stock(db, "NVDA")
    _insert_bars(db, aapl.id, _make_closes(260))
    _insert_bars(db, nvda.id, _make_closes(260, start=200.0, step=0.8))
    _insert_spy(db, _make_closes(260, start=400.0, step=0.2))
    _insert_regime(db)
    db.commit()

    svc = SetupService(db)
    count = svc.compute_and_store_all(today=_TODAY)
    assert count == 2

    rows = db.execute(select(SetupSnapshot)).scalars().all()
    assert len(rows) == 2
    tickers = {r.ticker for r in rows}
    assert tickers == {"AAPL", "NVDA"}
    for row in rows:
        assert row.scan_date == _TODAY
        assert row.setup_type is not None
        assert row.earnings_risk in ("SAFE", "CAUTION", "DANGER")
        assert isinstance(row.ready_signal, bool)
        assert row.rs_percentile is not None


# ── S17: cockpit_params import check ─────────────────────────────────────────

def test_s17_cockpit_params_import_and_validation() -> None:
    from app.services.cockpit.cockpit_params import SETUP, SHARED, REGIME
    # Pydantic frozen model: all fields accessible
    assert SETUP.MA_PERIODS == [10, 21, 50, 150, 200]
    assert SETUP.EARNINGS_DANGER_DAYS < SETUP.EARNINGS_CAUTION_DAYS
    assert SETUP.QUALITY_A_RS_MIN > SETUP.QUALITY_B_RS_MIN > SETUP.QUALITY_C_RS_MIN
    assert SETUP.READY_TREND_MIN >= 1
    assert SETUP.SETUP_RETENTION_DAYS == 60
