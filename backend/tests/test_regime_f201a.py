"""F201-a Market Regime data layer tests — Sprint Contract S1–S14."""
from __future__ import annotations

import json
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session

from app.models import Base
from app.models.market_index import MarketIndex
from app.models.market_regime_snapshot import MarketRegimeSnapshot
from app.repositories.market_regime_repository import MarketRegimeRepository
from app.services.cockpit.cockpit_params import REGIME, SHARED
from app.services.cockpit.market_regime_service import MarketRegimeService


# ── data helpers ─────────────────────────────────────────────────────────────

_START = date(2024, 1, 1)


def _insert_closes(db: Session, symbol: str, closes: list[float], start: date = _START) -> None:
    for i, close in enumerate(closes):
        d = start + timedelta(days=i)
        prev = closes[i - 1] if i > 0 else None
        pct = (close - prev) / prev * 100 if prev else None
        db.add(MarketIndex(symbol=symbol, name=symbol, date=d, close=close, prev_close=prev, change_pct=pct))
    db.commit()


def _bull_200() -> list[float]:
    """200 bars: golden cross + close > both MAs + 20d return >> 0."""
    return [100.0] * 199 + [120.0]


def _bull_200_low_vol() -> list[float]:
    """200 bars: golden cross + close > both MAs + 20d return < -5% (vol_score=0).

    bars 0-149: flat 50; bars 150-178: rise 100→180; bar 179: spike 190; bars 180-199: settle 180.
    """
    closes: list[float] = [50.0] * 150
    for j in range(29):
        closes.append(100.0 + j * (80.0 / 28.0))
    closes.append(190.0)   # closes[-21] = 190
    closes.extend([180.0] * 20)
    return closes  # 200 bars


def _bull_51() -> list[float]:
    """51 bars: close above MA50."""
    return [100.0] * 50 + [101.0]


def _bear_200() -> list[float]:
    """200 bars: death cross + close < both MAs + 20d return << -5%."""
    step = (50.0 - 200.0) / 199
    return [200.0 + i * step for i in range(200)]


def _bear_51() -> list[float]:
    """51 bars: close below MA50."""
    return [100.0] * 50 + [90.0]


def _iwm_rs_bull() -> list[float]:
    """200 bars with high close/MA50 ratio (> SPY _bull_200 ratio)."""
    return [100.0] * 199 + [140.0]


def _snapshot_data(d: date, score: int = 50, regime: str = "NEUTRAL") -> dict:
    return {
        "date": d,
        "regime": regime,
        "market_score": score,
        "spy_trend_score": 0,
        "qqq_trend_score": 0,
        "iwm_breadth_score": 0,
        "sector_participation_score": 0,
        "risk_appetite_score": 0,
        "volatility_stress_score": 0,
        "allowed_exposure_pct": REGIME.ALLOWED_EXPOSURE_PCT[regime],
        "single_trade_risk_pct": REGIME.SINGLE_TRADE_RISK_PCT[regime],
        "preferred_setups": json.dumps(REGIME.PREFERRED_SETUPS[regime]),
        "avoid_setups": json.dumps(REGIME.AVOID_SETUPS[regime]),
        "computed_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }


def _alembic_cfg(db_path: str) -> Config:
    backend_root = Path(__file__).resolve().parent.parent
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


# ── S1 / S2 — Alembic migration ──────────────────────────────────────────────

def test_s1_alembic_upgrade_creates_table() -> None:
    """S1: upgrade head → market_regime_snapshots + unique index exist."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        cfg = _alembic_cfg(str(db_path))
        command.upgrade(cfg, "head")
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            insp = inspect(engine)
            assert "market_regime_snapshots" in insp.get_table_names()
            uniques = insp.get_unique_constraints("market_regime_snapshots")
            assert any(u["name"] == "uq_market_regime_date" for u in uniques)
        finally:
            engine.dispose()


def test_s2_alembic_downgrade_removes_table() -> None:
    """S2: downgrade -1 → market_regime_snapshots is gone."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        cfg = _alembic_cfg(str(db_path))
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "008_f204_earnings_events")
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            assert "market_regime_snapshots" not in inspect(engine).get_table_names()
        finally:
            engine.dispose()


# ── S3 — full bull → score=100, RISK_ON ──────────────────────────────────────

def test_s3_full_bull_score_100(db_session: Session) -> None:
    """S3: all conditions bullish → market_score=100, regime=RISK_ON."""
    for sym in ["SPY", "QQQ"]:
        _insert_closes(db_session, sym, _bull_200())
    _insert_closes(db_session, "IWM", _iwm_rs_bull())
    for sym in SHARED.SECTOR_ETFS:
        _insert_closes(db_session, sym, _bull_51())

    snap = MarketRegimeService(db_session).compute_and_store(date(2026, 1, 1))
    assert snap.market_score == 100
    assert snap.regime == "RISK_ON"
    assert snap.spy_trend_score == 25
    assert snap.qqq_trend_score == 20
    assert snap.iwm_breadth_score == 15
    assert snap.sector_participation_score == 20
    assert snap.risk_appetite_score == 10
    assert snap.volatility_stress_score == 10


# ── S4 — full bear → score=0, RISK_OFF ───────────────────────────────────────

def test_s4_full_bear_score_0(db_session: Session) -> None:
    """S4: all conditions bearish → market_score=0, regime=RISK_OFF."""
    for sym in ["SPY", "QQQ", "IWM"]:
        _insert_closes(db_session, sym, _bear_200())
    for sym in SHARED.SECTOR_ETFS:
        _insert_closes(db_session, sym, _bear_51())

    snap = MarketRegimeService(db_session).compute_and_store(date(2026, 1, 1))
    assert snap.market_score == 0
    assert snap.regime == "RISK_OFF"


# ── S5 — SPY sub-score isolation ─────────────────────────────────────────────

def test_s5_spy_subscore_25_total_25(db_session: Session) -> None:
    """S5: golden cross SPY only, 20d return < -5% → spy=25, vol=0, total=25."""
    _insert_closes(db_session, "SPY", _bull_200_low_vol())

    snap = MarketRegimeService(db_session).compute_and_store(date(2026, 1, 1))
    assert snap.spy_trend_score == 25
    assert snap.qqq_trend_score == 0
    assert snap.iwm_breadth_score == 0
    assert snap.sector_participation_score == 0
    assert snap.risk_appetite_score == 0
    assert snap.volatility_stress_score == 0
    assert snap.market_score == 25


# ── S6 — sector participation 6/11 ───────────────────────────────────────────

def test_s6_sector_participation_6_of_11(db_session: Session) -> None:
    """S6: 6/11 sectors above MA50 → sector_participation_score = 11."""
    bull_syms = SHARED.SECTOR_ETFS[:6]
    bear_syms = SHARED.SECTOR_ETFS[6:]
    for sym in bull_syms:
        _insert_closes(db_session, sym, _bull_51())
    for sym in bear_syms:
        _insert_closes(db_session, sym, _bear_51())

    snap = MarketRegimeService(db_session).compute_and_store(date(2026, 1, 1))
    assert snap.sector_participation_score == round(6 / 11 * 20)  # 11


# ── S7 — IWM RS positive ─────────────────────────────────────────────────────

def test_s7_iwm_rs_positive_pts_counted(db_session: Session) -> None:
    """S7: IWM close/MA50 > SPY close/MA50 → IWM_RS_POSITIVE_PTS counted."""
    _insert_closes(db_session, "SPY", _bull_200())
    _insert_closes(db_session, "IWM", _iwm_rs_bull())

    snap = MarketRegimeService(db_session).compute_and_store(date(2026, 1, 1))
    # IWM above MA50 (+5) + above MA200 (+5) + RS positive (+5) = 15
    assert snap.iwm_breadth_score == 15


# ── S8 — regime threshold boundaries ─────────────────────────────────────────

@pytest.mark.parametrize("score,expected_regime", [
    (80, "RISK_ON"),
    (79, "CONSTRUCTIVE"),
    (60, "CONSTRUCTIVE"),
    (59, "NEUTRAL"),
    (40, "NEUTRAL"),
    (39, "DEFENSIVE"),
    (20, "DEFENSIVE"),
    (19, "RISK_OFF"),
    (0, "RISK_OFF"),
])
def test_s8_regime_thresholds(db_session: Session, score: int, expected_regime: str) -> None:
    """S8: regime thresholds at exact boundary values."""
    svc = MarketRegimeService(db_session)
    assert svc._classify_regime(score) == expected_regime


# ── S9 — upsert same date overwrites ─────────────────────────────────────────

def test_s9_upsert_same_date_overwrite(db_session: Session) -> None:
    """S9: upsert same date twice → 1 row, values from second call."""
    repo = MarketRegimeRepository(db_session)
    d = date(2026, 3, 1)
    repo.upsert(_snapshot_data(d, score=90, regime="RISK_ON"))
    repo.upsert(_snapshot_data(d, score=42, regime="NEUTRAL"))

    count = db_session.execute(select(func.count()).select_from(MarketRegimeSnapshot)).scalar()
    assert count == 1

    latest = repo.get_latest()
    assert latest is not None
    assert latest.market_score == 42
    assert latest.regime == "NEUTRAL"


# ── S10 — get_latest returns None when empty ─────────────────────────────────

def test_s10_get_latest_empty(db_session: Session) -> None:
    """S10: get_latest() on empty table returns None."""
    assert MarketRegimeRepository(db_session).get_latest() is None


# ── S11 — delete_old ─────────────────────────────────────────────────────────

def test_s11_delete_old(db_session: Session) -> None:
    """S11: delete_old(cutoff) removes dates < cutoff, keeps >= cutoff."""
    repo = MarketRegimeRepository(db_session)
    cutoff = date(2026, 2, 1)
    repo.upsert(_snapshot_data(date(2026, 1, 29)))  # < cutoff → deleted
    repo.upsert(_snapshot_data(date(2026, 1, 31)))  # < cutoff → deleted
    repo.upsert(_snapshot_data(date(2026, 2, 1)))   # = cutoff → kept
    repo.upsert(_snapshot_data(date(2026, 3, 1)))   # > cutoff → kept

    deleted = repo.delete_old(cutoff)
    assert deleted == 2

    remaining = db_session.execute(select(func.count()).select_from(MarketRegimeSnapshot)).scalar()
    assert remaining == 2


# ── S12 — insufficient data → spy_trend_score=0, no exception ────────────────

def test_s12_insufficient_spy_data(db_session: Session) -> None:
    """S12: SPY < 50 bars → spy_trend_score=0, no exception, others compute normally."""
    _insert_closes(db_session, "SPY", [100.0] * 49)  # 49 < MA_SHORT=50

    snap = MarketRegimeService(db_session).compute_and_store(date(2026, 1, 1))
    assert snap.spy_trend_score == 0


# ── S13 — get_indices_and_sectors_state structure ────────────────────────────

def test_s13_indices_sectors_state_structure(db_session: Session) -> None:
    """S13: correct return structure with all required keys."""
    for sym in [*SHARED.INDEX_ETFS, *SHARED.SECTOR_ETFS]:
        _insert_closes(db_session, sym, _bull_51())

    svc = MarketRegimeService(db_session)
    indices, sectors = svc.get_indices_and_sectors_state()

    assert len(indices) == len(SHARED.INDEX_ETFS)
    assert len(sectors) == len(SHARED.SECTOR_ETFS)

    index_keys = {"symbol", "close", "changePct", "aboveMa50", "aboveMa200", "rsTrend", "state"}
    sector_keys = {"symbol", "close", "changePct", "state"}

    for item in indices:
        assert set(item.keys()) == index_keys, f"index keys mismatch: {item.keys()}"

    for item in sectors:
        assert set(item.keys()) == sector_keys, f"sector keys mismatch: {item.keys()}"

    index_symbols = {i["symbol"] for i in indices}
    assert index_symbols == set(SHARED.INDEX_ETFS)

    sector_symbols = {s["symbol"] for s in sectors}
    assert sector_symbols == set(SHARED.SECTOR_ETFS)


# ── S14 — cockpit_params import validates cleanly ─────────────────────────────

def test_s14_cockpit_params_import_no_exception() -> None:
    """S14: cockpit_params module-level instances pass Pydantic validation."""
    from app.services.cockpit import cockpit_params  # noqa: F401
    from app.services.cockpit.cockpit_params import REGIME, SHARED

    assert SHARED.MA_SHORT == 50
    assert SHARED.MA_LONG == 200
    assert SHARED.REGIME_LOOKBACK_DAYS == 200
    assert len(SHARED.SECTOR_ETFS) == 11
    assert len(SHARED.INDEX_ETFS) == 4  # SPY/QQQ/IWM/VXX (VXX added as VIX proxy)

    assert REGIME.RISK_ON_MIN == 80
    assert REGIME.CONSTRUCTIVE_MIN == 60
    assert REGIME.NEUTRAL_MIN == 40
    assert REGIME.DEFENSIVE_MIN == 20

    # Verify exposure tables cover all regimes
    regimes = {"RISK_ON", "CONSTRUCTIVE", "NEUTRAL", "DEFENSIVE", "RISK_OFF"}
    assert set(REGIME.ALLOWED_EXPOSURE_PCT.keys()) == regimes
    assert set(REGIME.SINGLE_TRADE_RISK_PCT.keys()) == regimes
    assert set(REGIME.PREFERRED_SETUPS.keys()) == regimes
    assert set(REGIME.AVOID_SETUPS.keys()) == regimes
