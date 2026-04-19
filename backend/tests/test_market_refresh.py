from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pytest

from app.repositories.market_index_repository import (
    MARKET_INDEX_SYMBOLS,
    MARKET_INDEX_WINDOW,
    MarketIndexRepository,
)
from app.repositories.system_log_repository import SystemLogRepository
from app.services.market_refresh_service import MarketRefreshService


def _bar(y: int, m: int, d: int, close: float) -> dict:
    return {"date": date(y, m, d).isoformat(), "close": close}


# ---------- Repository ----------


def test_upsert_updates_same_symbol_date(db_session):
    repo = MarketIndexRepository(db_session)
    repo.upsert("SPX", "S&P 500", date(2026, 4, 15), 5200.0, 5180.0, 0.39)
    repo.upsert("SPX", "S&P 500", date(2026, 4, 15), 5201.5, 5180.0, 0.41)
    rows = repo.list_latest_by_symbol(["SPX"])
    assert len(rows) == 1
    assert rows[0].close == 5201.5


def test_list_latest_returns_one_per_symbol(db_session):
    repo = MarketIndexRepository(db_session)
    repo.upsert("SPX", "S&P 500", date(2026, 4, 14), 5100.0, 5090.0, 0.2)
    repo.upsert("SPX", "S&P 500", date(2026, 4, 15), 5200.0, 5100.0, 1.96)
    repo.upsert("NDX", "NASDAQ 100", date(2026, 4, 15), 18000.0, 17900.0, 0.56)
    repo.upsert("TNX", "10-Year Treasury Yield", date(2026, 4, 15), 4.25, 4.22, 0.71)
    rows = repo.list_latest_by_symbol()
    symbols = [r.symbol for r in rows]
    assert symbols == list(MARKET_INDEX_SYMBOLS)
    spx = next(r for r in rows if r.symbol == "SPX")
    assert spx.date == date(2026, 4, 15)


def test_prune_keeps_window(db_session):
    repo = MarketIndexRepository(db_session)
    for i in range(7):
        repo.upsert("SPX", "S&P 500", date(2026, 4, 1 + i), 5000.0 + i, None, None)
    deleted = repo.prune_to_window("SPX", MARKET_INDEX_WINDOW)
    assert deleted == 2

    from sqlalchemy import func, select

    from app.models.market_index import MarketIndex

    count = db_session.execute(
        select(func.count(MarketIndex.id)).where(MarketIndex.symbol == "SPX")
    ).scalar_one()
    assert count == MARKET_INDEX_WINDOW


# ---------- Service (with fake_fmp) ----------


def test_service_refresh_all_success(db_session, fake_fmp):
    fake_fmp.index_bars_results["^GSPC"] = [_bar(2026, 4, 14, 5100.0), _bar(2026, 4, 15, 5200.0)]
    fake_fmp.index_bars_results["^NDX"] = [_bar(2026, 4, 14, 17900.0), _bar(2026, 4, 15, 18000.0)]
    fake_fmp.treasury_result = {
        "date": "2026-04-15",
        "year10": 4.25,
        "prev_date": "2026-04-14",
        "prev_year10": 4.22,
    }

    svc = MarketRefreshService(db_session, fmp=fake_fmp)  # type: ignore[arg-type]
    batch = svc.refresh_all()

    assert batch.completed == 3
    assert batch.failed == 0
    # Service must translate DB symbols to FMP symbols before calling fmp client.
    called_symbols = [call[0] for call in fake_fmp.index_bars_calls]
    assert called_symbols == ["^GSPC", "^NDX"]

    rows = MarketIndexRepository(db_session).list_latest_by_symbol()
    by_sym = {r.symbol: r for r in rows}
    assert by_sym["SPX"].close == 5200.0
    assert by_sym["SPX"].prev_close == 5100.0
    assert by_sym["SPX"].change_pct == pytest.approx(1.9608, abs=1e-3)
    assert by_sym["NDX"].change_pct == pytest.approx(0.5587, abs=1e-3)
    assert by_sym["TNX"].close == 4.25
    assert by_sym["TNX"].prev_close == 4.22
    assert by_sym["TNX"].change_pct == pytest.approx(0.7109, abs=1e-3)


def test_service_isolates_per_symbol_failure(db_session, fake_fmp):
    fake_fmp.index_bars_results["^GSPC"] = [_bar(2026, 4, 15, 5200.0)]
    fake_fmp.index_bars_exc["^NDX"] = RuntimeError("boom")
    fake_fmp.treasury_result = {
        "date": "2026-04-15",
        "year10": 4.25,
        "prev_date": None,
        "prev_year10": None,
    }

    svc = MarketRefreshService(db_session, fmp=fake_fmp)  # type: ignore[arg-type]
    batch = svc.refresh_all()

    assert batch.completed == 2
    assert batch.failed == 1
    statuses = {r.symbol: r.status for r in batch.results}
    assert statuses == {"SPX": "ok", "NDX": "error", "TNX": "ok"}

    logs = SystemLogRepository(db_session).list_recent(level="ERROR")
    assert any("NDX" in log.message for log in logs)

    row = MarketIndexRepository(db_session).list_latest_by_symbol(["SPX"])[0]
    assert row.prev_close is None
    assert row.change_pct is None


def test_service_empty_bars_is_error(db_session, fake_fmp):
    fake_fmp.index_bars_results["^GSPC"] = []
    fake_fmp.index_bars_results["^NDX"] = [_bar(2026, 4, 15, 18000.0)]
    fake_fmp.treasury_result = {
        "date": "2026-04-15",
        "year10": 4.25,
        "prev_date": None,
        "prev_year10": None,
    }
    svc = MarketRefreshService(db_session, fmp=fake_fmp)  # type: ignore[arg-type]
    batch = svc.refresh_all()
    assert batch.failed == 1
    assert next(r for r in batch.results if r.symbol == "SPX").status == "error"


# ---------- refresh_job wiring ----------


def test_refresh_job_invokes_market_refresh(monkeypatch, session_engine):
    from sqlalchemy.orm import sessionmaker

    from app.services import refresh_job as rj_mod

    TestingSession = sessionmaker(bind=session_engine, autoflush=False, autocommit=False)

    from app.models import Stock

    with TestingSession() as seed:
        seed.add(Stock(ticker="AAPL", name="Apple", is_active=True, added_at=datetime.now(timezone.utc)))
        seed.commit()

    class StubDataSvc:
        def __init__(self, db, fmp):
            self.db = db

        def refresh_all(self, ids):
            return {"total": len(ids), "completed": len(ids), "failed": 0, "results": []}

        def purge_old_logs(self):
            return 0

    calls = {"market": 0}

    class StubMarketSvc:
        def __init__(self, db, fmp):
            pass

        def refresh_all(self):
            calls["market"] += 1

            from app.services.market_refresh_service import MarketBatchResult

            return MarketBatchResult(completed=3, failed=0, results=[])

    monkeypatch.setattr(rj_mod, "DataRefreshService", StubDataSvc)
    monkeypatch.setattr(rj_mod, "MarketRefreshService", StubMarketSvc)

    mgr = rj_mod.RefreshJobManager()
    res = mgr.start_refresh(TestingSession, lambda: object())
    assert res.status == "started"

    if mgr._thread is not None:
        mgr._thread.join(timeout=5.0)

    state = mgr.get_status()
    assert state.status == "completed"
    assert calls["market"] == 1


def test_refresh_job_market_failure_does_not_fail_job(monkeypatch, session_engine):
    from sqlalchemy.orm import sessionmaker

    from app.services import refresh_job as rj_mod

    TestingSession = sessionmaker(bind=session_engine, autoflush=False, autocommit=False)

    from app.models import Stock

    with TestingSession() as seed:
        seed.add(Stock(ticker="AAPL", name="Apple", is_active=True, added_at=datetime.now(timezone.utc)))
        seed.commit()

    class StubDataSvc:
        def __init__(self, db, fmp):
            pass

        def refresh_all(self, ids):
            return {"total": len(ids), "completed": len(ids), "failed": 0, "results": []}

        def purge_old_logs(self):
            return 0

    class ExplodingMarketSvc:
        def __init__(self, db, fmp):
            pass

        def refresh_all(self):
            raise RuntimeError("market boom")

    monkeypatch.setattr(rj_mod, "DataRefreshService", StubDataSvc)
    monkeypatch.setattr(rj_mod, "MarketRefreshService", ExplodingMarketSvc)

    mgr = rj_mod.RefreshJobManager()
    mgr.start_refresh(TestingSession, lambda: object())
    if mgr._thread is not None:
        mgr._thread.join(timeout=5.0)

    assert mgr.get_status().status == "completed"
