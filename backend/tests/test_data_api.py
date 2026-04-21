from __future__ import annotations

import threading
import time
from datetime import date, datetime, timezone

import pytest

from app.models import Stock, SystemLog
from app.services import refresh_job
from app.services.refresh_job import (
    DAILY_REFRESH_CRON,
    RefreshJobManager,
    RefreshJobState,
    SCHEDULER_JOB_ID,
    start_scheduler,
    shutdown_scheduler,
)


@pytest.fixture(autouse=True)
def _reset_refresh_state():
    refresh_job.manager = RefreshJobManager()
    shutdown_scheduler()
    yield
    shutdown_scheduler()


def _fmp_bar(d: date, close: float = 100.0) -> dict:
    return {
        "date": d.isoformat(),
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": 10_000,
    }


def _seed_stock(db_session, ticker: str = "AAPL") -> Stock:
    s = Stock(ticker=ticker, name=f"{ticker} Inc", is_active=True)
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


def _attach_bars(fake_fmp, ticker: str, n: int):
    """Give FakeFMP a get_daily_bars method returning n fake bars for ticker."""
    today = datetime.now(timezone.utc).date()
    fake_fmp.get_daily_bars = lambda t, f, to_, _bars=[
        _fmp_bar(today, close=100.0) for _ in range(n)
    ]: _bars if t.upper() == ticker.upper() else []


class TestRefreshStatusIdle:
    def test_status_idle_when_no_job(self, client):
        resp = client.get("/api/data/status")
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["status"] == "idle"
        assert body["jobId"] is None
        assert body["progress"] == {"total": 0, "completed": 0, "failed": 0}
        assert body["startedAt"] is None
        assert body["lastRefreshedAt"] is None


class TestTriggerRefresh:
    def test_post_refresh_returns_202(self, client, db_session, fake_fmp):
        _seed_stock(db_session, "AAPL")
        _seed_stock(db_session, "MSFT")
        _attach_bars(fake_fmp, "AAPL", 3)

        resp = client.post("/api/data/refresh")
        assert resp.status_code == 202
        body = resp.json()["data"]
        assert body["status"] in {"started", "in_progress"}
        assert body["jobId"].startswith("refresh-")
        assert body["totalStocks"] == 2

        _wait_for_completion()

    def test_second_refresh_while_running_returns_in_progress(self, client, db_session, fake_fmp):
        _seed_stock(db_session, "AAPL")
        # Block first refresh by making FMP slow
        gate = threading.Event()

        def slow_bars(t, f, to_):
            gate.wait(timeout=2)
            return []

        fake_fmp.get_daily_bars = slow_bars

        resp1 = client.post("/api/data/refresh")
        assert resp1.status_code == 202
        first_job = resp1.json()["data"]["jobId"]

        # Second call while worker is blocked
        resp2 = client.post("/api/data/refresh")
        assert resp2.status_code == 202
        body2 = resp2.json()["data"]
        assert body2["status"] == "in_progress"
        assert body2["jobId"] == first_job

        gate.set()
        _wait_for_completion()

    def test_status_reflects_completed(self, client, db_session, fake_fmp):
        _seed_stock(db_session, "AAPL")
        _attach_bars(fake_fmp, "AAPL", 3)

        client.post("/api/data/refresh")
        _wait_for_completion()

        resp = client.get("/api/data/status")
        body = resp.json()["data"]
        assert body["status"] == "completed"
        assert body["progress"]["total"] == 1
        assert body["progress"]["completed"] == 1
        assert body["progress"]["failed"] == 0
        assert body["lastRefreshedAt"] is not None


class TestCamelCaseResponse:
    def test_status_response_is_camel_case(self, client):
        resp = client.get("/api/data/status")
        body = resp.json()["data"]
        for key in ("jobId", "status", "progress", "startedAt", "lastRefreshedAt"):
            assert key in body


class TestAddStockBackfillHook:
    def test_add_stock_triggers_backfill_and_creates_bars(self, client, fake_fmp):
        ticker = "AAPL"
        fake_fmp.search_results = [
            {"symbol": ticker, "name": "Apple", "exchangeShortName": "NASDAQ", "type": "stock"}
        ]
        _attach_bars(fake_fmp, ticker, 10)

        resp = client.post("/api/watchlist", json={"ticker": ticker})
        assert resp.status_code == 201

        # Verify daily_bars were persisted
        list_resp = client.get("/api/watchlist")
        item = list_resp.json()["data"][0]
        assert item["ticker"] == ticker
        # 10 bars < 150 threshold → "insufficient"
        assert item["dataStatus"] == "insufficient"

    def test_add_stock_logs_warn_when_backfill_fails(self, client, fake_fmp, db_session):
        ticker = "BBBB"
        fake_fmp.search_results = [
            {"symbol": ticker, "name": "Broken", "exchangeShortName": "NASDAQ", "type": "stock"}
        ]

        def boom(t, f, to_):
            raise RuntimeError("fmp unreachable")

        fake_fmp.get_daily_bars = boom

        resp = client.post("/api/watchlist", json={"ticker": ticker})
        assert resp.status_code == 201

        warns = db_session.query(SystemLog).filter_by(level="WARN").all()
        assert any(ticker in w.message for w in warns)


class TestScheduler:
    def test_start_scheduler_registers_cron_job(self):
        sched = start_scheduler(
            session_factory=lambda: None,
            fmp_factory=lambda: None,
            autostart=False,
        )
        jobs = sched.get_jobs()
        job_ids = {j.id for j in jobs}
        # F003 watchlist refresh + F105 scanner + F105 universe refresh (D042/D038)
        assert SCHEDULER_JOB_ID in job_ids
        assert "ma150_market_scanner" in job_ids
        assert "ma150_universe_refresh" in job_ids
        assert DAILY_REFRESH_CRON == "30 21 * * 1-5"

    def test_start_scheduler_is_idempotent(self):
        s1 = start_scheduler(lambda: None, lambda: None, autostart=False)
        s2 = start_scheduler(lambda: None, lambda: None, autostart=False)
        assert s1 is s2


class TestConcurrentStart:
    def test_concurrent_start_creates_single_job(self, db_session, fake_fmp):
        _seed_stock(db_session, "AAPL")
        _attach_bars(fake_fmp, "AAPL", 3)

        mgr = RefreshJobManager()

        def factory():
            # fresh session per caller
            from tests.conftest import sessionmaker  # type: ignore

            return None  # see below

        # Use the existing db_session's bind
        session_factory = lambda: type(db_session)(bind=db_session.bind)  # noqa: E731

        results = []
        threads = [
            threading.Thread(
                target=lambda: results.append(
                    mgr.start_refresh(session_factory=session_factory, fmp_factory=lambda: fake_fmp)
                )
            )
            for _ in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2)

        # Wait for worker completion
        for _ in range(50):
            if mgr.get_status().status in {"completed", "failed"}:
                break
            time.sleep(0.05)

        started_count = sum(1 for r in results if r.status == "started")
        assert started_count == 1
        assert sum(1 for r in results if r.status == "in_progress") == 9


def _wait_for_completion(timeout: float = 3.0) -> RefreshJobState:
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = refresh_job.manager.get_status()
        if state.status in {"completed", "failed"}:
            return state
        time.sleep(0.02)
    raise AssertionError(f"refresh did not complete; state={refresh_job.manager.get_status()}")
