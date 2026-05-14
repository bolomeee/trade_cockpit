"""Integration tests for GET /api/cockpit/chart/{ticker}/weekly (F216-c1).

Covers sprint contract §3 standards 1-9:
  1   Valid schema (ticker / weeklyBars / weeklyMas / stage)
  2   weeklyBars length and OHLCV fields, ascending date order
  3   weeklyMas keys {"10", "30", "40"}, series length = bars - period + 1
  4   Stage 2 fixture: stage=2, slope30w>0.5, MA fields non-null, scanDate set
  5   < 4 daily bars → weeklyBars=[], MAs empty, stage=0, scanDate=null, all numerics null
  6   ≥4 bars but <30 weeks → weeklyBars non-empty, stage=0, scanDate non-null
  7   Unknown ticker → 404 NOT_FOUND
  8   weeks=5 → 422; weeks=100 → 422; weeks=10 → 200; weeks=50 → 200
  9   GET /weekly does NOT write rows to weekly_stage_snapshots (pure compute)
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyBar, Stock, WeeklyStageSnapshot

_START = date(2025, 1, 6)  # Monday — safe base for ISO-week grouping


# ── helpers ───────────────────────────────────────────────────────────────────

def _add_stock(db: Session, ticker: str) -> Stock:
    stock = Stock(ticker=ticker, name=f"{ticker} Corp", is_active=True)
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


def _add_daily_bars(
    db: Session,
    stock_id: int,
    n_weeks: int,
    base_close: float = 100.0,
    delta_per_week: float = 1.0,
) -> None:
    """5 daily bars per week, Mon-Fri, with close = base_close + week * delta_per_week."""
    bars = []
    for week in range(n_weeks):
        close = base_close + week * delta_per_week
        for day in range(5):
            bars.append(
                DailyBar(
                    stock_id=stock_id,
                    date=_START + timedelta(weeks=week, days=day),
                    open=close,
                    high=close + 1.0,
                    low=close - 1.0,
                    close=close,
                    volume=1_000_000,
                )
            )
    db.add_all(bars)
    db.commit()


# ── Standard 1 + 2 + 3 ───────────────────────────────────────────────────────

def test_weekly_chart_valid_schema(client: TestClient, db_session: Session) -> None:
    """Standards 1-3: shape, length, MA keys, ascending order."""
    stock = _add_stock(db_session, "SCHM")
    _add_daily_bars(db_session, stock.id, n_weeks=45)

    resp = client.get("/api/cockpit/chart/SCHM/weekly")
    assert resp.status_code == 200

    body = resp.json()
    assert body["message"] == "success"
    data = body["data"]

    # Standard 1: top-level keys
    assert data["ticker"] == "SCHM"
    assert isinstance(data["weeklyBars"], list)
    assert isinstance(data["weeklyMas"], dict)
    assert "stage" in data

    # Standard 2: 45 weeks aggregated, default weeks=50 → return all 45
    assert len(data["weeklyBars"]) == 45
    bar = data["weeklyBars"][0]
    for field in ("date", "open", "high", "low", "close", "volume"):
        assert field in bar, f"missing field {field!r} in weeklyBars item"
    # ascending order
    assert data["weeklyBars"][-1]["date"] > data["weeklyBars"][0]["date"]

    # Standard 3: MA keys present; series length = n - period + 1 (or 0 if short)
    assert set(data["weeklyMas"].keys()) == {"10", "30", "40"}
    assert len(data["weeklyMas"]["10"]) == 45 - 10 + 1  # 36
    assert len(data["weeklyMas"]["30"]) == 45 - 30 + 1  # 16
    assert len(data["weeklyMas"]["40"]) == 45 - 40 + 1  # 6


# ── Standard 4 ───────────────────────────────────────────────────────────────

def test_weekly_chart_stage2(client: TestClient, db_session: Session) -> None:
    """Standard 4: ≥30 weeks uptrend → stage=2, slope30w>0.5, MA fields set, scanDate ok."""
    stock = _add_stock(db_session, "STAG")
    # 45 weeks with +1.0/week → close[-1]=144, 30wMA[-1]≈129.5, slope_30w≈0.79% > 0.5
    _add_daily_bars(db_session, stock.id, n_weeks=45, base_close=100.0, delta_per_week=1.0)

    resp = client.get("/api/cockpit/chart/STAG/weekly")
    assert resp.status_code == 200

    data = resp.json()["data"]
    stage = data["stage"]

    assert stage["stage"] == 2
    assert stage["slope30W"] is not None
    assert stage["slope30W"] > 0.5
    assert stage["weeklyMa10"] is not None
    assert stage["weeklyMa30"] is not None
    assert stage["weeklyMa40"] is not None
    assert stage["scanDate"] is not None
    # scan_date must equal the last weekly bar's date
    assert stage["scanDate"] == data["weeklyBars"][-1]["date"]


# ── Standard 5 ───────────────────────────────────────────────────────────────

def test_weekly_chart_too_few_bars(client: TestClient, db_session: Session) -> None:
    """Standard 5: < 4 daily bars → empty result, stage=0, all numerics null, scanDate null."""
    stock = _add_stock(db_session, "TINY")
    for day in range(3):  # only 3 bars, below MIN_DAILY_BARS_FOR_WEEKLY=4
        db_session.add(
            DailyBar(
                stock_id=stock.id,
                date=_START + timedelta(days=day),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=500,
            )
        )
    db_session.commit()

    resp = client.get("/api/cockpit/chart/TINY/weekly")
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["weeklyBars"] == []
    assert data["weeklyMas"] == {"10": [], "30": [], "40": []}

    stage = data["stage"]
    assert stage["stage"] == 0
    assert stage["scanDate"] is None
    for field in ("weeklyClose", "weeklyMa10", "weeklyMa30", "weeklyMa40", "slope30W"):
        assert stage[field] is None, f"expected null for {field!r}"


# ── Standard 6 ───────────────────────────────────────────────────────────────

def test_weekly_chart_insufficient_for_stage(client: TestClient, db_session: Session) -> None:
    """Standard 6: 15 weeks — enough bars, but < 30 → stage=0, weeklyBars non-empty, scanDate set."""
    stock = _add_stock(db_session, "SLIM")
    _add_daily_bars(db_session, stock.id, n_weeks=15)

    resp = client.get("/api/cockpit/chart/SLIM/weekly")
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert len(data["weeklyBars"]) == 15

    stage = data["stage"]
    assert stage["stage"] == 0
    assert stage["scanDate"] is not None
    assert stage["scanDate"] == data["weeklyBars"][-1]["date"]


# ── Standard 7 ───────────────────────────────────────────────────────────────

def test_weekly_chart_unknown_ticker(client: TestClient) -> None:
    """Standard 7: ticker not in DB → 404 NOT_FOUND."""
    resp = client.get("/api/cockpit/chart/UNKNOWN/weekly")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "NOT_FOUND"


# ── Standard 8 ───────────────────────────────────────────────────────────────

def test_weekly_chart_weeks_validation(client: TestClient, db_session: Session) -> None:
    """Standard 8: weeks out of [10, 50] → 422; boundary values → 200."""
    stock = _add_stock(db_session, "VALD")
    _add_daily_bars(db_session, stock.id, n_weeks=45)

    # out-of-range
    r5 = client.get("/api/cockpit/chart/VALD/weekly?weeks=5")
    assert r5.status_code == 422
    assert r5.json()["error"]["code"] == "VALIDATION_ERROR"

    r100 = client.get("/api/cockpit/chart/VALD/weekly?weeks=100")
    assert r100.status_code == 422
    assert r100.json()["error"]["code"] == "VALIDATION_ERROR"

    # boundary values must succeed
    assert client.get("/api/cockpit/chart/VALD/weekly?weeks=10").status_code == 200
    assert client.get("/api/cockpit/chart/VALD/weekly?weeks=50").status_code == 200


# ── Standard 9 ───────────────────────────────────────────────────────────────

def test_weekly_chart_pure_compute_no_db_write(client: TestClient, db_session: Session) -> None:
    """Standard 9: GET /weekly must not insert rows into weekly_stage_snapshots."""
    stock = _add_stock(db_session, "PURE")
    _add_daily_bars(db_session, stock.id, n_weeks=45)

    def _count() -> int:
        return len(
            db_session.execute(
                select(WeeklyStageSnapshot).where(WeeklyStageSnapshot.ticker == "PURE")
            )
            .scalars()
            .all()
        )

    before = _count()
    client.get("/api/cockpit/chart/PURE/weekly")
    assert _count() == before, "GET /weekly must not write to weekly_stage_snapshots"
