from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select

from app.models.market_breakout_scan import MarketBreakoutScan
from app.models.market_scan_universe import MarketScanUniverse
from app.repositories.market_breakout_repository import (
    BreakoutScanRow,
    MarketBreakoutRepository,
)
from app.repositories.system_log_repository import SystemLogRepository
from app.services.market_scanner_service import MarketScannerService


# ---------- fixtures / helpers ----------


def _seed_universe(db, tickers: list[tuple[str, str, int]]) -> None:
    now = datetime.now(timezone.utc)
    for ticker, name, mc in tickers:
        db.add(
            MarketScanUniverse(
                ticker=ticker,
                company_name=name,
                exchange="NASDAQ",
                market_cap=mc,
                last_seen_at=now,
                added_at=now,
            )
        )
    db.commit()


def _sma_series_breakout(n: int = 25, pct_above: float = 2.0) -> dict:
    """SMA-source payload that satisfies the breakout rule on the last bar."""
    bars = []
    for i in range(n):
        sma = 80.0 + i * 1.0
        close = sma - 5.0  # close below sma (no premature breakout)
        bars.append({"date": f"2026-03-{i + 1:02d}", "close": close, "sma": sma})
    # prev: close<sma (already true); today: close = sma*(1+pct/100)
    last_sma = bars[-1]["sma"]
    bars[-1]["close"] = last_sma * (1 + pct_above / 100.0)
    return {"source": "sma", "bars": bars}


def _sma_series_no_cross(n: int = 25) -> dict:
    """close always >= sma — no upward cross on last bar."""
    bars = []
    for i in range(n):
        sma = 80.0 + i * 1.0
        close = sma + 1.0
        bars.append({"date": f"2026-03-{i + 1:02d}", "close": close, "sma": sma})
    return {"source": "sma", "bars": bars}


def _sma_series_negative_slope() -> dict:
    """SMA monotonically decreasing → slope ≤ 0."""
    bars = []
    for i in range(25):
        sma = 100.0 - i * 1.0
        close = sma - 5.0
        bars.append({"date": f"2026-03-{i + 1:02d}", "close": close, "sma": sma})
    last_sma = bars[-1]["sma"]
    bars[-1]["close"] = last_sma * 1.02  # satisfies cross + pct, but slope<0 still rejects
    return {"source": "sma", "bars": bars}


def _eod_series_breakout(n: int = 180, pct_above: float = 2.0) -> dict:
    """EOD-fallback payload — caller must have ≥150 bars for MA150 + 20 for slope."""
    bars = []
    # Uptrending closes so MA150 slope positive; keep close below MA150 until last.
    # Use linear ramp: close = 50 + 0.1 * i → MA150[i=149] = avg(50..64.9) = ~57.45
    for i in range(n):
        close = 50.0 + 0.1 * i
        bars.append({"date": f"2025-{(i // 30) + 1:02d}-{(i % 30) + 1:02d}", "close": close, "sma": None})
    # Force the last bar to cross upward from below MA.
    # At i=n-1, MA150 ≈ avg of last 150 closes ≈ 50 + 0.1 * (n-75). For n=180: ≈ 60.5.
    # Set prev close = MA_prev - 1; today close = MA_today * (1 + pct/100).
    # We don't know exact MA until runtime; scanner computes it. Use relative magnitudes.
    bars[-2]["close"] = 50.0  # clearly below any recent average
    # Today: make close a large value so pct_above may exceed 10 — we want ≤10% actually.
    # Compute target via approximation of MA150_today = mean of closes from n-150..n-1.
    # We'll set bars[-1]["close"] post-hoc below.
    window = bars[-150:]
    ma_today_est = sum(b["close"] for b in window[:-1]) / 150.0  # close_today not yet finalized
    # Iterate once: assume close_today = ma_today_est*(1+pct)
    close_today = ma_today_est * (1 + pct_above / 100.0)
    # Recompute MA with this close included (replace placeholder)
    bars[-1]["close"] = close_today
    window = bars[-150:]
    ma_today = sum(b["close"] for b in window) / 150.0
    # Adjust once more to hit target pct_above
    bars[-1]["close"] = ma_today * (1 + pct_above / 100.0)
    return {"source": "eod_fallback", "bars": bars}


# ---------- tests ----------


def test_scan_cold_start_triggers_universe_refresh(db_session, fake_fmp):
    # Universe empty; screener returns 1 stock; that stock's MA150 series satisfies breakout.
    fake_fmp.screener_universe_result = [
        {"symbol": "AAPL", "companyName": "Apple", "exchange": "NASDAQ", "marketCap": 3_000_000_000_000},
    ]
    fake_fmp.ma150_results["AAPL"] = _sma_series_breakout()

    result = MarketScannerService(db_session, fake_fmp).run_scan()

    assert result.status == "ok"
    assert fake_fmp.screener_universe_calls == 1
    assert fake_fmp.ma150_calls == ["AAPL"]
    assert db_session.execute(select(func.count(MarketScanUniverse.id))).scalar_one() == 1

    logs = SystemLogRepository(db_session).list_recent(level="OK")
    assert any(l.source == "universe_refresher" for l in logs)


def test_scan_cold_start_universe_failure_aborts(db_session, fake_fmp):
    fake_fmp.screener_universe_exc = RuntimeError("fmp down")

    result = MarketScannerService(db_session, fake_fmp).run_scan()

    assert result.status == "error"
    assert fake_fmp.ma150_calls == []  # scan never runs
    assert db_session.execute(select(func.count(MarketBreakoutScan.id))).scalar_one() == 0


def test_scan_happy_path_sma_source_hits_breakout_rule(db_session, fake_fmp):
    _seed_universe(db_session, [
        ("AAPL", "Apple Inc.", 3_000_000_000_000),
        ("MSFT", "Microsoft", 2_800_000_000_000),
    ])
    fake_fmp.ma150_results["AAPL"] = _sma_series_breakout(pct_above=2.0)
    # MSFT: pct=20% → should reject
    fake_fmp.ma150_results["MSFT"] = _sma_series_breakout(pct_above=20.0)

    result = MarketScannerService(db_session, fake_fmp).run_scan()

    assert result.status == "ok"
    assert result.scanned == 2
    assert result.hits == 1

    rows = db_session.execute(select(MarketBreakoutScan)).scalars().all()
    assert len(rows) == 1
    assert rows[0].ticker == "AAPL"
    assert rows[0].company_name == "Apple Inc."  # from universe, not FMP
    assert rows[0].market_cap == 3_000_000_000_000
    assert rows[0].pct_above_ma150 < 5.0
    assert rows[0].slope_value > 0


def test_scan_rejects_pct_above_10_percent(db_session, fake_fmp):
    _seed_universe(db_session, [("AAPL", "Apple", 3_000_000_000_000)])
    fake_fmp.ma150_results["AAPL"] = _sma_series_breakout(pct_above=12.0)

    result = MarketScannerService(db_session, fake_fmp).run_scan()

    assert result.hits == 0


def test_scan_rejects_negative_slope(db_session, fake_fmp):
    _seed_universe(db_session, [("AAPL", "Apple", 3_000_000_000_000)])
    fake_fmp.ma150_results["AAPL"] = _sma_series_negative_slope()

    result = MarketScannerService(db_session, fake_fmp).run_scan()

    assert result.hits == 0


def test_scan_rejects_no_crossover(db_session, fake_fmp):
    _seed_universe(db_session, [("AAPL", "Apple", 3_000_000_000_000)])
    fake_fmp.ma150_results["AAPL"] = _sma_series_no_cross()

    result = MarketScannerService(db_session, fake_fmp).run_scan()

    assert result.hits == 0


def test_scan_eod_fallback_computes_ma_locally_and_logs_warn_once(db_session, fake_fmp):
    _seed_universe(db_session, [
        ("AAA", "Alpha Corp", 100_000_000_000),
        ("BBB", "Beta Corp", 100_000_000_000),
    ])
    fake_fmp.ma150_results["AAA"] = _eod_series_breakout(pct_above=2.0)
    fake_fmp.ma150_results["BBB"] = _eod_series_breakout(pct_above=2.0)

    result = MarketScannerService(db_session, fake_fmp).run_scan()

    assert result.status == "ok"
    assert result.fallback_used is True
    assert result.hits == 2

    warn_logs = SystemLogRepository(db_session).list_recent(level="WARN")
    scanner_warns = [l for l in warn_logs if l.source == "market_scanner"]
    assert len(scanner_warns) == 1  # deduped across tickers


def test_scan_per_ticker_failure_isolated(db_session, fake_fmp):
    _seed_universe(db_session, [
        ("AAPL", "Apple", 3_000_000_000_000),
        ("MSFT", "Microsoft", 2_800_000_000_000),
    ])
    fake_fmp.ma150_results["AAPL"] = _sma_series_breakout(pct_above=2.0)
    fake_fmp.ma150_exc["MSFT"] = RuntimeError("boom")

    result = MarketScannerService(db_session, fake_fmp).run_scan()

    assert result.scanned == 1
    assert result.failed == 1
    assert result.hits == 1

    err_logs = SystemLogRepository(db_session).list_recent(level="ERROR")
    assert any("MSFT" in l.message and l.source == "market_scanner" for l in err_logs)

    rows = db_session.execute(select(MarketBreakoutScan)).scalars().all()
    assert [r.ticker for r in rows] == ["AAPL"]


def test_scan_total_failure_preserves_old_snapshot(db_session, fake_fmp):
    _seed_universe(db_session, [
        ("AAPL", "Apple", 3_000_000_000_000),
        ("MSFT", "Microsoft", 2_800_000_000_000),
    ])
    # Seed an old snapshot (3 rows)
    repo = MarketBreakoutRepository(db_session)
    old_scan_date = date(2026, 4, 20)
    scanned_at = datetime(2026, 4, 20, 22, 15, tzinfo=timezone.utc)
    repo.replace_scan([
        BreakoutScanRow(
            scan_date=old_scan_date, ticker=t, company_name=f"{t} Inc.",
            signal_type="legacy_crossover",
            close_price=100.0, ma150_value=99.0, pct_above_ma150=1.0,
            slope_value=0.5, market_cap=10_000_000_000, scanned_at=scanned_at,
        )
        for t in ("OLD1", "OLD2", "OLD3")
    ])

    fake_fmp.ma150_exc["AAPL"] = RuntimeError("boom")
    fake_fmp.ma150_exc["MSFT"] = RuntimeError("boom")

    result = MarketScannerService(db_session, fake_fmp).run_scan()

    assert result.status == "error"
    assert result.failed == 2
    assert result.hits == 0

    # Old snapshot preserved
    count = db_session.execute(select(func.count(MarketBreakoutScan.id))).scalar_one()
    assert count == 3


def test_scan_empty_hits_still_overwrites(db_session, fake_fmp):
    _seed_universe(db_session, [("AAPL", "Apple", 3_000_000_000_000)])
    # Seed old snapshot
    repo = MarketBreakoutRepository(db_session)
    repo.replace_scan([
        BreakoutScanRow(
            scan_date=date(2026, 4, 20), ticker="OLD", company_name="Old Co.",
            signal_type="legacy_crossover",
            close_price=10.0, ma150_value=9.0, pct_above_ma150=1.0,
            slope_value=0.5, market_cap=10_000_000_000,
            scanned_at=datetime.now(timezone.utc),
        )
    ])
    # Today's scan: no hits (no crossover)
    fake_fmp.ma150_results["AAPL"] = _sma_series_no_cross()

    result = MarketScannerService(db_session, fake_fmp).run_scan()

    assert result.status == "ok"
    assert result.scanned == 1
    assert result.hits == 0

    count = db_session.execute(select(func.count(MarketBreakoutScan.id))).scalar_one()
    assert count == 0  # old snapshot cleared


def test_scan_uses_universe_row_company_and_market_cap(db_session, fake_fmp):
    _seed_universe(db_session, [("AAPL", "Apple Inc.", 3_123_456_789_012)])
    fake_fmp.ma150_results["AAPL"] = _sma_series_breakout(pct_above=2.0)

    MarketScannerService(db_session, fake_fmp).run_scan()

    row = db_session.execute(select(MarketBreakoutScan)).scalar_one()
    assert row.company_name == "Apple Inc."
    assert row.market_cap == 3_123_456_789_012


def test_scan_list_active_filters_by_last_seen(db_session, fake_fmp):
    """Rows with older last_seen_at are excluded from scanning (D038)."""
    now = datetime.now(timezone.utc)
    stale = now - timedelta(days=45)
    db_session.add(MarketScanUniverse(
        ticker="STALE", company_name="Old", exchange="NASDAQ",
        market_cap=100_000_000_000, last_seen_at=stale, added_at=stale,
    ))
    db_session.add(MarketScanUniverse(
        ticker="FRESH", company_name="New", exchange="NASDAQ",
        market_cap=100_000_000_000, last_seen_at=now, added_at=now,
    ))
    db_session.commit()

    fake_fmp.ma150_results["FRESH"] = _sma_series_breakout(pct_above=2.0)

    result = MarketScannerService(db_session, fake_fmp).run_scan()

    assert fake_fmp.ma150_calls == ["FRESH"]
    assert result.hits == 1


# ---------- refresh_job wiring ----------


def test_refresh_job_registers_scanner_and_universe_jobs(session_engine):
    from sqlalchemy.orm import sessionmaker

    from app.services import refresh_job as rj_mod

    TestingSession = sessionmaker(bind=session_engine, autoflush=False, autocommit=False)
    try:
        sched = rj_mod.start_scheduler(
            TestingSession, lambda: object(), autostart=False
        )
        try:
            assert sched.get_job(rj_mod.SCHEDULER_JOB_ID) is not None
            scanner_job = sched.get_job(rj_mod.SCANNER_JOB_ID)
            universe_job = sched.get_job(rj_mod.UNIVERSE_JOB_ID)
            assert scanner_job is not None
            assert universe_job is not None
            # Trigger fields reflect settings defaults
            scanner_fields = {f.name: f for f in scanner_job.trigger.fields}
            assert str(scanner_fields["day_of_week"]) == "mon-fri"
            assert str(scanner_fields["hour"]) == "6"
            assert str(scanner_fields["minute"]) == "15"
            universe_fields = {f.name: f for f in universe_job.trigger.fields}
            assert str(universe_fields["day"]) == "1"
            assert str(universe_fields["hour"]) == "5"
            assert str(universe_fields["minute"]) == "0"
        finally:
            rj_mod.shutdown_scheduler()
    finally:
        rj_mod.shutdown_scheduler()


# ---------- F105-a5: concurrency ----------


def test_scan_runs_workers_in_parallel(db_session):
    """Concurrent scan must be measurably faster than serial for a slow FMP mock.

    Each ticker's fake FMP call sleeps 200ms. With 6 workers, 12 tickers
    should finish in ~400ms (2 waves × 200ms), well under the serial 2400ms.
    Also asserts observed concurrency peak equals SCAN_WORKER_COUNT.
    """
    import threading
    import time

    from app.services.market_scanner_service import MarketScannerService
    from app.services.scanner_params import SCAN_WORKER_COUNT

    tickers = [(f"T{i:02d}", f"Co {i}", 100_000_000_000) for i in range(12)]
    _seed_universe(db_session, tickers)

    inflight = {"n": 0, "peak": 0}
    lock = threading.Lock()

    class SlowFMP:
        def __init__(self) -> None:
            self.ma150_calls: list[str] = []

        def get_ma150_series_or_eod(self, symbol: str) -> dict:
            with lock:
                inflight["n"] += 1
                inflight["peak"] = max(inflight["peak"], inflight["n"])
                self.ma150_calls.append(symbol)
            try:
                time.sleep(0.2)
            finally:
                with lock:
                    inflight["n"] -= 1
            return _sma_series_no_cross()  # no hit — keeps assertions simple

    fmp = SlowFMP()
    start = time.monotonic()
    result = MarketScannerService(db_session, fmp).run_scan()
    elapsed = time.monotonic() - start

    assert result.status == "ok"
    assert result.scanned == 12
    assert result.hits == 0
    assert inflight["peak"] == SCAN_WORKER_COUNT, (
        f"expected concurrency peak {SCAN_WORKER_COUNT}, got {inflight['peak']}"
    )
    # Serial bound: 12 × 200ms = 2.4s; concurrent bound: 2 waves × 200ms ≈ 0.4s.
    # Give generous headroom for CI jitter.
    assert elapsed < 1.2, f"scan took {elapsed:.2f}s, expected <1.2s"


def test_scan_ok_log_includes_duration_and_workers(db_session, fake_fmp):
    """OK log line carries duration_s and workers=... for observability (F105-a5)."""
    _seed_universe(db_session, [("AAPL", "Apple", 3_000_000_000_000)])
    fake_fmp.ma150_results["AAPL"] = _sma_series_breakout(pct_above=2.0)

    MarketScannerService(db_session, fake_fmp).run_scan()

    ok_logs = SystemLogRepository(db_session).list_recent(level="OK")
    scanner_ok = [l for l in ok_logs if l.source == "market_scanner"]
    assert scanner_ok, "expected OK log from market_scanner"
    msg = scanner_ok[0].message
    assert "duration_s=" in msg
    assert "workers=6" in msg


def test_scan_preserves_d040_semantics_under_concurrency(db_session):
    """All 6 tickers raise → no snapshot clear, status=error."""
    tickers = [(f"X{i}", f"X {i}", 100_000_000_000) for i in range(6)]
    _seed_universe(db_session, tickers)

    class FailingFMP:
        def __init__(self) -> None:
            self.ma150_calls: list[str] = []

        def get_ma150_series_or_eod(self, symbol: str) -> dict:
            self.ma150_calls.append(symbol)
            raise RuntimeError(f"boom {symbol}")

    # Seed a prior snapshot so we can confirm it survives.
    scan_date = date(2026, 4, 20)
    scanned_at = datetime(2026, 4, 20, 6, 20, tzinfo=timezone.utc)
    MarketBreakoutRepository(db_session).replace_scan([
        BreakoutScanRow(
            scan_date=scan_date,
            ticker="OLD",
            company_name="Old Co",
            signal_type="legacy_crossover",
            close_price=10.0,
            ma150_value=9.0,
            pct_above_ma150=11.0,
            slope_value=0.1,
            market_cap=100_000_000_000,
            scanned_at=scanned_at,
        )
    ])

    from app.services.market_scanner_service import MarketScannerService

    result = MarketScannerService(db_session, FailingFMP()).run_scan()

    assert result.status == "error"
    assert result.failed == 6
    # Old snapshot preserved (D040).
    remaining = db_session.execute(select(MarketBreakoutScan)).scalars().all()
    assert len(remaining) == 1
    assert remaining[0].ticker == "OLD"
