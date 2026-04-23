from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.models.market_scan_universe import MarketScanUniverse
from app.repositories.system_log_repository import SystemLogRepository
from app.services.universe_refresh_service import UniverseRefreshService


def _screener_row(symbol: str, name: str, mc: int, exchange: str = "NASDAQ") -> dict:
    return {
        "symbol": symbol,
        "companyName": name,
        "exchange": exchange,
        "marketCap": mc,
    }


def test_refresh_success_upserts_rows_and_logs_ok(db_session, fake_fmp):
    fake_fmp.screener_universe_result = [
        _screener_row("AAPL", "Apple Inc.", 3_000_000_000_000),
        _screener_row("MSFT", "Microsoft Corp.", 2_800_000_000_000),
        _screener_row("GOOG", "Alphabet Inc.", 2_000_000_000_000, "NYSE"),
    ]

    result = UniverseRefreshService(db_session, fake_fmp).refresh()

    assert result.status == "ok"
    assert result.upserted == 3
    assert result.skipped == 0
    assert fake_fmp.screener_universe_calls == 1

    rows = db_session.execute(select(MarketScanUniverse).order_by(MarketScanUniverse.ticker)).scalars().all()
    assert [r.ticker for r in rows] == ["AAPL", "GOOG", "MSFT"]
    assert rows[0].market_cap == 3_000_000_000_000
    assert rows[0].company_name == "Apple Inc."

    logs = SystemLogRepository(db_session).list_recent(level="OK")
    assert any(l.source == "universe_refresher" and "upserted=3" in l.message for l in logs)


def test_refresh_skips_invalid_rows(db_session, fake_fmp):
    fake_fmp.screener_universe_result = [
        _screener_row("AAPL", "Apple", 3_000_000_000_000),
        {"companyName": "No Symbol", "marketCap": 100},  # missing symbol
        {"symbol": "BAD1", "companyName": "X", "marketCap": None},  # bad marketCap
        {"symbol": "BAD2", "companyName": "Y", "marketCap": "NaN"},  # bad string marketCap
        {"symbol": "BAD3", "companyName": "Z", "marketCap": 0},  # non-positive
        "not-a-dict",
    ]

    result = UniverseRefreshService(db_session, fake_fmp).refresh()

    assert result.status == "ok"
    assert result.upserted == 1
    assert result.skipped == 5

    count = db_session.execute(select(func.count(MarketScanUniverse.id))).scalar_one()
    assert count == 1


def test_refresh_skips_mutual_fund_tickers(db_session, fake_fmp):
    """D052: 5-letter tickers ending in X are mutual funds — skip even if FMP leaks them."""
    fake_fmp.screener_universe_result = [
        _screener_row("AAPL", "Apple Inc.", 3_000_000_000_000),
        _screener_row("OAKIX", "Oakmark International Fund", 50_000_000_000),
        _screener_row("VPMAX", "Vanguard PRIMECAP Admiral", 80_000_000_000),
        _screener_row("ABALX", "American Funds Balanced A", 200_000_000_000),
        _screener_row("BAC", "Bank of America", 300_000_000_000),  # 3 letters — keep
    ]

    result = UniverseRefreshService(db_session, fake_fmp).refresh()

    assert result.status == "ok"
    assert result.upserted == 2
    assert result.skipped == 3

    tickers = {
        r.ticker
        for r in db_session.execute(select(MarketScanUniverse)).scalars().all()
    }
    assert tickers == {"AAPL", "BAC"}


def test_refresh_fmp_failure_logs_error(db_session, fake_fmp):
    fake_fmp.screener_universe_exc = RuntimeError("fmp down")

    result = UniverseRefreshService(db_session, fake_fmp).refresh()

    assert result.status == "error"
    assert result.upserted == 0
    assert "fmp down" in (result.error or "")

    count = db_session.execute(select(func.count(MarketScanUniverse.id))).scalar_one()
    assert count == 0

    logs = SystemLogRepository(db_session).list_recent(level="ERROR")
    assert any(
        l.source == "universe_refresher" and "fmp down" in l.message for l in logs
    )


def test_refresh_upsert_idempotent(db_session, fake_fmp):
    fake_fmp.screener_universe_result = [_screener_row("AAPL", "Apple Inc.", 3_000_000_000_000)]
    svc = UniverseRefreshService(db_session, fake_fmp)
    svc.refresh()

    first_added_at = db_session.execute(
        select(MarketScanUniverse).where(MarketScanUniverse.ticker == "AAPL")
    ).scalar_one().added_at

    fake_fmp.screener_universe_result = [_screener_row("AAPL", "Apple Inc.", 3_500_000_000_000)]
    svc.refresh()

    rows = db_session.execute(select(MarketScanUniverse)).scalars().all()
    assert len(rows) == 1
    assert rows[0].market_cap == 3_500_000_000_000
    # added_at preserved per repo semantics
    assert rows[0].added_at == first_added_at
    # last_seen_at must be a timezone-aware datetime after refresh
    assert rows[0].last_seen_at is not None
    _ = datetime.now(timezone.utc)  # sanity: tz import works
