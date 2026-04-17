from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from app.external.polygon_client import PolygonClient
from app.repositories.market_index_repository import (
    MARKET_INDEX_SYMBOLS,
    MARKET_INDEX_WINDOW,
    MarketIndexRepository,
)
from app.repositories.system_log_repository import SystemLogRepository
from app.services.market_refresh_service import MarketRefreshService


def _ts(year: int, month: int, day: int) -> int:
    return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp() * 1000)


def _bar(y: int, m: int, d: int, close: float) -> SimpleNamespace:
    return SimpleNamespace(timestamp=_ts(y, m, d), close=close)


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

    from app.models.market_index import MarketIndex
    from sqlalchemy import func, select

    count = db_session.execute(
        select(func.count(MarketIndex.id)).where(MarketIndex.symbol == "SPX")
    ).scalar_one()
    assert count == MARKET_INDEX_WINDOW


# ---------- Service (with FakeMarketPolygon) ----------


class FakeMarketPolygon:
    def __init__(self) -> None:
        self.index_calls: list[str] = []
        self.index_returns: dict[str, list[Any]] = {}
        self.index_exc: dict[str, Exception] = {}
        self.treasury_return: dict[str, Any] | None = None
        self.treasury_exc: Exception | None = None

    def get_index_recent_aggs(self, symbol: str, days: int = 10) -> list[Any]:
        self.index_calls.append(symbol)
        if symbol in self.index_exc:
            raise self.index_exc[symbol]
        return self.index_returns.get(symbol, [])

    def get_treasury_10y_latest(self) -> dict[str, Any]:
        if self.treasury_exc is not None:
            raise self.treasury_exc
        assert self.treasury_return is not None
        return self.treasury_return


def test_service_refresh_all_success(db_session):
    polygon = FakeMarketPolygon()
    polygon.index_returns["SPX"] = [_bar(2026, 4, 14, 5100.0), _bar(2026, 4, 15, 5200.0)]
    polygon.index_returns["NDX"] = [_bar(2026, 4, 14, 17900.0), _bar(2026, 4, 15, 18000.0)]
    polygon.treasury_return = {
        "date": "2026-04-15",
        "yield_10_year": 4.25,
        "prev_date": "2026-04-14",
        "prev_yield_10_year": 4.22,
    }

    svc = MarketRefreshService(db_session, polygon=polygon)  # type: ignore[arg-type]
    batch = svc.refresh_all()

    assert batch.completed == 3
    assert batch.failed == 0
    assert polygon.index_calls == ["SPX", "NDX"]

    rows = MarketIndexRepository(db_session).list_latest_by_symbol()
    by_sym = {r.symbol: r for r in rows}
    assert by_sym["SPX"].close == 5200.0
    assert by_sym["SPX"].prev_close == 5100.0
    assert by_sym["SPX"].change_pct == pytest.approx(1.9608, abs=1e-3)
    assert by_sym["NDX"].change_pct == pytest.approx(0.5587, abs=1e-3)
    assert by_sym["TNX"].close == 4.25
    assert by_sym["TNX"].prev_close == 4.22
    assert by_sym["TNX"].change_pct == pytest.approx(0.7109, abs=1e-3)


def test_service_isolates_per_symbol_failure(db_session):
    polygon = FakeMarketPolygon()
    polygon.index_returns["SPX"] = [_bar(2026, 4, 15, 5200.0)]
    polygon.index_exc["NDX"] = RuntimeError("boom")
    polygon.treasury_return = {
        "date": "2026-04-15",
        "yield_10_year": 4.25,
        "prev_date": None,
        "prev_yield_10_year": None,
    }

    svc = MarketRefreshService(db_session, polygon=polygon)  # type: ignore[arg-type]
    batch = svc.refresh_all()

    assert batch.completed == 2
    assert batch.failed == 1
    statuses = {r.symbol: r.status for r in batch.results}
    assert statuses == {"SPX": "ok", "NDX": "error", "TNX": "ok"}

    logs = SystemLogRepository(db_session).list_recent(level="ERROR")
    assert any("NDX" in log.message for log in logs)

    # SPX with only 1 bar → prev_close / change_pct None
    row = MarketIndexRepository(db_session).list_latest_by_symbol(["SPX"])[0]
    assert row.prev_close is None
    assert row.change_pct is None


def test_service_empty_aggs_is_error(db_session):
    polygon = FakeMarketPolygon()
    polygon.index_returns["SPX"] = []
    polygon.index_returns["NDX"] = [_bar(2026, 4, 15, 18000.0)]
    polygon.treasury_return = {
        "date": "2026-04-15",
        "yield_10_year": 4.25,
        "prev_date": None,
        "prev_yield_10_year": None,
    }
    svc = MarketRefreshService(db_session, polygon=polygon)  # type: ignore[arg-type]
    batch = svc.refresh_all()
    assert batch.failed == 1
    assert next(r for r in batch.results if r.symbol == "SPX").status == "error"


# ---------- PolygonClient HTTP layer ----------


def test_polygon_treasury_parses_results(monkeypatch):
    class FakeResponse:
        def __init__(self, payload: dict[str, Any]) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return self._payload

    captured: dict[str, Any] = {}

    def _transport_handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json={
                "results": [
                    {"date": "2026-04-15", "yield_10_year": 4.25},
                    {"date": "2026-04-14", "yield_10_year": 4.22},
                ],
                "status": "OK",
            },
        )

    transport = httpx.MockTransport(_transport_handler)
    http = httpx.Client(base_url="https://api.polygon.io", transport=transport)

    # Bypass rate-limit sleeping and SDK init
    monkeypatch.setattr(
        "app.external.polygon_client.RESTClient", lambda api_key: object()
    )
    client = PolygonClient(api_key="fake", _sleep=lambda _t: None, _http_client=http)
    result = client.get_treasury_10y_latest()

    assert result == {
        "date": "2026-04-15",
        "yield_10_year": 4.25,
        "prev_date": "2026-04-14",
        "prev_yield_10_year": 4.22,
    }
    assert "/fed/v1/treasury-yields" in captured["url"]
    assert "apiKey=fake" in captured["url"]
    assert "sort=date.desc" in captured["url"]


def test_polygon_index_recent_aggs_prefixes_symbol(monkeypatch):
    calls: dict[str, Any] = {}

    class FakeRest:
        def __init__(self, api_key: str) -> None:
            pass

        def list_aggs(self, **kwargs):
            calls.update(kwargs)
            return iter([_bar(2026, 4, 14, 5100.0), _bar(2026, 4, 15, 5200.0)])

    monkeypatch.setattr("app.external.polygon_client.RESTClient", FakeRest)
    client = PolygonClient(api_key="fake", _sleep=lambda _t: None)
    bars = client.get_index_recent_aggs("SPX", days=5)

    assert len(bars) == 2
    assert calls["ticker"] == "I:SPX"
    assert calls["timespan"] == "day"
    assert calls["adjusted"] is True


# ---------- refresh_job wiring ----------


def test_refresh_job_invokes_market_refresh(monkeypatch, session_engine):
    from sqlalchemy.orm import sessionmaker

    from app.services import refresh_job as rj_mod

    TestingSession = sessionmaker(bind=session_engine, autoflush=False, autocommit=False)

    # Seed one active stock so DataRefreshService has something to iterate
    from app.models import Stock

    with TestingSession() as seed:
        seed.add(Stock(ticker="AAPL", name="Apple", is_active=True, added_at=datetime.now(timezone.utc)))
        seed.commit()

    class StubDataSvc:
        def __init__(self, db, polygon):
            self.db = db

        def refresh_all(self, ids):
            return {"total": len(ids), "completed": len(ids), "failed": 0, "results": []}

        def purge_old_logs(self):
            return 0

    calls = {"market": 0}

    class StubMarketSvc:
        def __init__(self, db, polygon):
            pass

        def refresh_all(self):
            calls["market"] += 1

            # Return a minimal result-shaped object
            from app.services.market_refresh_service import MarketBatchResult

            return MarketBatchResult(completed=3, failed=0, results=[])

    monkeypatch.setattr(rj_mod, "DataRefreshService", StubDataSvc)
    monkeypatch.setattr(rj_mod, "MarketRefreshService", StubMarketSvc)

    mgr = rj_mod.RefreshJobManager()
    res = mgr.start_refresh(TestingSession, lambda: object())
    assert res.status == "started"

    # Wait for worker thread
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
        def __init__(self, db, polygon):
            pass

        def refresh_all(self, ids):
            return {"total": len(ids), "completed": len(ids), "failed": 0, "results": []}

        def purge_old_logs(self):
            return 0

    class ExplodingMarketSvc:
        def __init__(self, db, polygon):
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
