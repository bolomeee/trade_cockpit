from __future__ import annotations

from datetime import date, datetime, timezone

from app.repositories.market_breakout_repository import (
    BreakoutScanRow,
    MarketBreakoutRepository,
)
from app.repositories.market_index_repository import MarketIndexRepository


def _row(
    *,
    scan_date: date,
    ticker: str,
    pct: float,
    scanned_at: datetime,
    company_name: str = "Example Inc.",
    signal_type: str = "a1_stage_breakout",
    close_price: float = 100.0,
    ma150_value: float = 90.0,
    slope_value: float = 0.5,
    market_cap: int = 100_000_000_000,
) -> BreakoutScanRow:
    return BreakoutScanRow(
        scan_date=scan_date,
        ticker=ticker,
        company_name=company_name,
        signal_type=signal_type,
        close_price=close_price,
        ma150_value=ma150_value,
        pct_above_ma150=pct,
        slope_value=slope_value,
        market_cap=market_cap,
        scanned_at=scanned_at,
    )


def test_overview_empty(client):
    resp = client.get("/api/market/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"data": [], "message": "success"}


def test_overview_returns_three_in_order(client, db_session):
    repo = MarketIndexRepository(db_session)
    # Insert in non-canonical order to verify API ordering.
    repo.upsert("TNX", "10-Year Treasury Yield", date(2026, 4, 15), 4.25, 4.22, 0.71)
    repo.upsert("SPX", "S&P 500", date(2026, 4, 15), 5200.5, 5180.2, 0.39)
    repo.upsert("NDX", "NASDAQ 100", date(2026, 4, 15), 18200.3, 18050.1, 0.83)

    resp = client.get("/api/market/overview")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert [d["symbol"] for d in data] == ["SPX", "NDX", "TNX"]

    spx = data[0]
    assert set(spx.keys()) == {"symbol", "name", "close", "prevClose", "changePct", "date"}
    assert spx["name"] == "S&P 500"
    assert spx["close"] == 5200.5
    assert spx["prevClose"] == 5180.2
    assert spx["changePct"] == 0.39
    assert spx["date"] == "2026-04-15"


def test_overview_partial_symbols(client, db_session):
    MarketIndexRepository(db_session).upsert(
        "SPX", "S&P 500", date(2026, 4, 15), 5200.5, None, None
    )
    resp = client.get("/api/market/overview")
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["symbol"] == "SPX"
    assert data[0]["prevClose"] is None
    assert data[0]["changePct"] is None


def test_overview_latest_per_symbol(client, db_session):
    repo = MarketIndexRepository(db_session)
    repo.upsert("SPX", "S&P 500", date(2026, 4, 14), 5100.0, 5090.0, 0.2)
    repo.upsert("SPX", "S&P 500", date(2026, 4, 15), 5200.0, 5100.0, 1.96)
    resp = client.get("/api/market/overview")
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["date"] == "2026-04-15"
    assert data[0]["close"] == 5200.0


# ---------- F105-a4: GET /api/market/breakouts ----------


def test_breakouts_empty_returns_null_scan_date(client):
    resp = client.get("/api/market/breakouts")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "data": {"scanDate": None, "scannedAt": None, "items": [], "total": 0},
        "message": "success",
    }


def test_breakouts_returns_latest_snapshot_sorted_asc(client, db_session):
    scan_date = date(2026, 4, 20)
    scanned_at = datetime(2026, 4, 20, 13, 0, tzinfo=timezone.utc)
    MarketBreakoutRepository(db_session).replace_scan(
        [
            _row(scan_date=scan_date, ticker="AAA", pct=8.2, scanned_at=scanned_at),
            _row(scan_date=scan_date, ticker="BBB", pct=1.5, scanned_at=scanned_at),
            _row(scan_date=scan_date, ticker="CCC", pct=4.7, scanned_at=scanned_at),
        ]
    )

    resp = client.get("/api/market/breakouts")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 3
    assert [it["ticker"] for it in data["items"]] == ["BBB", "CCC", "AAA"]
    assert [it["pctAboveMa150"] for it in data["items"]] == [1.5, 4.7, 8.2]
    assert set(data["items"][0].keys()) == {
        "ticker",
        "companyName",
        "signalType",
        "closePrice",
        "ma150Value",
        "pctAboveMa150",
        "slopeValue",
        "volume",
        "volumeRatio20",
        "marketCap",
    }


def test_breakouts_only_latest_scan_date(client, db_session):
    repo = MarketBreakoutRepository(db_session)
    old_date = date(2026, 4, 19)
    old_at = datetime(2026, 4, 19, 13, 0, tzinfo=timezone.utc)
    repo.replace_scan(
        [
            _row(scan_date=old_date, ticker="OLD1", pct=2.0, scanned_at=old_at),
            _row(scan_date=old_date, ticker="OLD2", pct=3.0, scanned_at=old_at),
        ]
    )
    new_date = date(2026, 4, 20)
    new_at = datetime(2026, 4, 20, 13, 0, tzinfo=timezone.utc)
    repo.replace_scan(
        [_row(scan_date=new_date, ticker="NEW", pct=5.0, scanned_at=new_at)]
    )

    resp = client.get("/api/market/breakouts")
    data = resp.json()["data"]
    assert data["scanDate"] == "2026-04-20"
    assert data["total"] == 1
    assert [it["ticker"] for it in data["items"]] == ["NEW"]


def test_breakouts_rounds_prices_to_two_decimals(client, db_session):
    scan_date = date(2026, 4, 20)
    scanned_at = datetime(2026, 4, 20, 13, 0, tzinfo=timezone.utc)
    MarketBreakoutRepository(db_session).replace_scan(
        [
            _row(
                scan_date=scan_date,
                ticker="RND",
                pct=4.7013,
                scanned_at=scanned_at,
                close_price=850.5051,
                ma150_value=812.309,
                market_cap=123_456_789_012,
            )
        ]
    )

    resp = client.get("/api/market/breakouts")
    item = resp.json()["data"]["items"][0]
    assert item["closePrice"] == 850.51
    assert item["ma150Value"] == 812.31
    assert item["pctAboveMa150"] == 4.70
    assert item["marketCap"] == 123_456_789_012


def test_breakouts_response_envelope_shape(client, db_session):
    scan_date = date(2026, 4, 20)
    scanned_at = datetime(2026, 4, 20, 13, 0, tzinfo=timezone.utc)
    MarketBreakoutRepository(db_session).replace_scan(
        [_row(scan_date=scan_date, ticker="ENV", pct=1.0, scanned_at=scanned_at)]
    )

    body = client.get("/api/market/breakouts").json()
    assert set(body.keys()) == {"data", "message"}
    assert body["message"] == "success"
    assert set(body["data"].keys()) == {"scanDate", "scannedAt", "items", "total"}
