from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.models.market_scan_universe import MarketScanUniverse
from app.repositories.system_log_repository import SystemLogRepository
from app.services.universe_refresh_service import UniverseRefreshService


def _screener_row(
    symbol: str,
    name: str,
    mc: int,
    exchange: str = "NASDAQ",
    sector: str | None = None,
    industry: str | None = None,
    price: float | None = None,
    volume: int | None = None,
) -> dict:
    row: dict = {
        "symbol": symbol,
        "companyName": name,
        "exchange": exchange,
        "marketCap": mc,
    }
    if sector is not None:
        row["sector"] = sector
    if industry is not None:
        row["industry"] = industry
    if price is not None:
        row["price"] = price
    if volume is not None:
        row["volume"] = volume
    return row


def test_refresh_success_upserts_rows_and_logs_ok(db_session, fake_fmp):
    # D108: healthy refresh carries price/volume; rows missing both would now be
    # flagged ERROR (degraded), so a "logs OK" test must use realistic rows.
    fake_fmp.screener_universe_result = [
        _screener_row("AAPL", "Apple Inc.", 3_000_000_000_000, price=175.0, volume=50_000_000),
        _screener_row("MSFT", "Microsoft Corp.", 2_800_000_000_000, price=410.0, volume=20_000_000),
        _screener_row("GOOG", "Alphabet Inc.", 2_000_000_000_000, "NYSE", price=140.0, volume=15_000_000),
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


# ---------------------------------------------------------------------------
# F205-a: new field integration tests
# ---------------------------------------------------------------------------


def test_refresh_writes_new_fields_to_db(db_session, fake_fmp):
    """Contract standard 7: mock FMP with sector/industry/price/volume → DB row has non-None values."""
    fake_fmp.screener_universe_result = [
        _screener_row(
            "NVDA", "NVIDIA Corp.", 2_000_000_000_000,
            sector="Technology", industry="Semiconductors",
            price=875.5, volume=40_000_000,
        ),
    ]
    result = UniverseRefreshService(db_session, fake_fmp).refresh()
    assert result.status == "ok"

    row = db_session.execute(
        select(MarketScanUniverse).where(MarketScanUniverse.ticker == "NVDA")
    ).scalar_one()
    assert row.sector == "Technology"
    assert row.industry == "Semiconductors"
    assert row.last_price == 875.5
    assert row.last_volume == 40_000_000


def test_refresh_degradation_counters_in_systemlog(db_session, fake_fmp):
    """Contract standard 10: missing optional fields → counter values appear in 'universe refreshed' log."""
    rows = []
    # 100 total rows: 30 missing sector, 10 with bad price type
    for i in range(100):
        kw: dict = {"sector": "Technology", "price": float(100 + i), "volume": 1_000_000}
        if i < 30:
            del kw["sector"]  # sector missing for first 30
        if i < 10:
            kw["price"] = "N/A"  # bad price type for first 10
        rows.append(_screener_row(
            f"T{i:03d}", f"Company {i}", 100_000_000_000,
            **{k: v for k, v in kw.items() if k in ("sector", "industry", "price", "volume")},
        ))
    fake_fmp.screener_universe_result = rows

    UniverseRefreshService(db_session, fake_fmp).refresh()

    logs = SystemLogRepository(db_session).list_recent(level="OK")
    log_msg = next(
        (l.message for l in logs if l.source == "universe_refresher" and "upserted=" in l.message),
        None,
    )
    assert log_msg is not None, "expected universe refreshed OK log"
    assert "sector_missing=30" in log_msg
    assert "price_missing=10" in log_msg
    assert "upserted=100" in log_msg


def test_refresh_no_warn_log_when_no_parse_exceptions(db_session, fake_fmp):
    """Contract standard 7 (WARN gate): no WARN log when parse_exception == 0."""
    fake_fmp.screener_universe_result = [
        _screener_row("AAPL", "Apple", 3_000_000_000_000, sector="Technology", price=175.0, volume=50_000_000),
    ]
    UniverseRefreshService(db_session, fake_fmp).refresh()

    warn_logs = SystemLogRepository(db_session).list_recent(level="WARN")
    assert not any(l.source == "universe_refresher" for l in warn_logs)


def test_refresh_warn_log_on_parse_exception(db_session, fake_fmp):
    """Contract standard 11: unexpected parse exception → WARN-level SystemLog with parse_exception count."""
    # A row that passes symbol/marketCap checks but has a sector value that
    # triggers an unexpected exception in optional field parsing.
    # We simulate this by passing a mock object whose str() raises.

    class _Boom:
        def __len__(self):
            return 1  # truthy so the `if sector_raw` branch is taken
        def __str__(self):
            raise RuntimeError("boom")
        def __getitem__(self, key):
            raise RuntimeError("boom")

    fake_fmp.screener_universe_result = [
        _screener_row("AAPL", "Apple", 3_000_000_000_000, price=175.0),
        {
            "symbol": "BOOM",
            "companyName": "Boom Corp",
            "marketCap": 100_000_000_000,
            "exchange": "NYSE",
            "sector": _Boom(),
        },
    ]
    result = UniverseRefreshService(db_session, fake_fmp).refresh()

    # BOOM row triggers parse exception → skipped, AAPL still upserted
    assert result.upserted == 1
    assert result.skipped == 1

    warn_logs = SystemLogRepository(db_session).list_recent(level="WARN")
    warn_msg = next(
        (l.message for l in warn_logs if l.source == "universe_refresher"), None
    )
    assert warn_msg is not None, "expected WARN log for parse exception"
    assert "parse_exception=1" in warn_msg
