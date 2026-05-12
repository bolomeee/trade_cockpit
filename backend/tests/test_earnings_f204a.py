"""Tests for F204-a Earnings Calendar data layer.

Covers Sprint Contract 标准 3–11:
  3. upsert_batch 写入 10 条不同 (ticker, date) 记录
  4. upsert_batch 更新已有记录的 eps_estimate
  5. upsert_batch 写入 eps_actual=None 时不覆盖已有 actual（关键业务规则）
  6. upsert_batch 写入 eps_actual 非 None 时覆盖
  7. get_next_earnings 返回最近一条未来记录
  8. get_next_earnings 无未来记录时返回 None
  9. FakeFMP.get_earnings_calendar 被正确调用（路径 + 参数）
 10. EarningsService.fetch_and_store 以 FakeFMP 写入 DB
 11. EarningsService.get_next_earnings 返回 camelCase dict
"""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta

import pytest

from app.models import EarningsEvent
from app.repositories.earnings_event_repository import EarningsEventRepository
from app.services.cockpit.earnings_service import EarningsService


# ─────────────────────────── helpers ────────────────────────────────────────

def _make_record(
    ticker: str = "AAPL",
    earnings_date: date = date(2026, 5, 1),
    eps_estimate: float | None = 1.5,
    eps_actual: float | None = None,
    revenue_estimate: int | None = 90_000_000_000,
    revenue_actual: int | None = None,
    time_of_day: str | None = "AMC",
) -> dict:
    return {
        "ticker": ticker,
        "earnings_date": earnings_date,
        "eps_estimate": eps_estimate,
        "eps_actual": eps_actual,
        "revenue_estimate": revenue_estimate,
        "revenue_actual": revenue_actual,
        "time_of_day": time_of_day,
        "fetched_at": datetime.now(timezone.utc),
    }


def _make_fmp_item(
    symbol: str = "AAPL",
    event_date: str = "2026-05-22",
    eps_estimated: float | None = 1.5,
    eps: float | None = None,
    revenue_estimated: int | None = 90_000_000_000,
    revenue: int | None = None,
    time: str = "AMC",
) -> dict:
    return {
        "symbol": symbol,
        "date": event_date,
        "epsEstimated": eps_estimated,
        "eps": eps,
        "revenueEstimated": revenue_estimated,
        "revenue": revenue,
        "time": time,
    }


# ─────────────────── 标准 3: upsert 10 条不同记录 ────────────────────────────

def test_upsert_batch_inserts_new_records(db_session):
    """标准 3: 10 条不同 (ticker, date) → DB 有 10 行."""
    repo = EarningsEventRepository(db_session)
    records = [
        _make_record(ticker=f"T{i:02d}", earnings_date=date(2026, 5, i + 1))
        for i in range(10)
    ]
    count = repo.upsert_batch(records)
    assert count == 10
    assert db_session.query(EarningsEvent).count() == 10


# ─────────────────── 标准 4: 更新 eps_estimate ───────────────────────────────

def test_upsert_batch_updates_estimate_on_conflict(db_session):
    """标准 4: 相同 (ticker, date) 再次 upsert，eps_estimate 被更新."""
    repo = EarningsEventRepository(db_session)
    repo.upsert_batch([_make_record(eps_estimate=1.5)])

    repo.upsert_batch([_make_record(eps_estimate=1.8)])

    row = db_session.query(EarningsEvent).filter_by(ticker="AAPL").first()
    assert row is not None
    assert db_session.query(EarningsEvent).count() == 1
    assert row.eps_estimate == pytest.approx(1.8)


# ─────────────────── 标准 5: actual=None 时不覆盖旧值 ────────────────────────

def test_upsert_batch_preserves_actual_when_new_value_is_none(db_session):
    """标准 5（关键）: eps_actual=None 的新记录不应覆盖已有的 eps_actual."""
    repo = EarningsEventRepository(db_session)
    # 初始写入 eps_actual=1.62
    repo.upsert_batch([_make_record(eps_actual=1.62)])

    # 再次 upsert，eps_actual=None（模拟 FMP 尚未回填）
    repo.upsert_batch([_make_record(eps_actual=None)])

    row = db_session.query(EarningsEvent).filter_by(ticker="AAPL").first()
    assert row is not None
    assert row.eps_actual == pytest.approx(1.62), "已有 eps_actual 不应被 None 覆盖"


def test_upsert_batch_preserves_revenue_actual_when_new_value_is_none(db_session):
    """标准 5 补充: revenue_actual=None 不应覆盖已有值."""
    repo = EarningsEventRepository(db_session)
    repo.upsert_batch([_make_record(revenue_actual=95_000_000_000)])
    repo.upsert_batch([_make_record(revenue_actual=None)])

    row = db_session.query(EarningsEvent).filter_by(ticker="AAPL").first()
    assert row.revenue_actual == 95_000_000_000


# ─────────────────── 标准 6: actual 非 None 时覆盖 ───────────────────────────

def test_upsert_batch_updates_actual_when_new_value_is_not_none(db_session):
    """标准 6: eps_actual 非 None 时应覆盖旧值."""
    repo = EarningsEventRepository(db_session)
    repo.upsert_batch([_make_record(eps_actual=1.50)])
    repo.upsert_batch([_make_record(eps_actual=1.62)])

    row = db_session.query(EarningsEvent).filter_by(ticker="AAPL").first()
    assert row.eps_actual == pytest.approx(1.62)


# ─────────────────── 标准 7: get_next_earnings 最近一条 ─────────────────────

def test_get_next_earnings_returns_nearest_future(db_session):
    """标准 7: 有多条未来记录时返回日期最近的一条."""
    repo = EarningsEventRepository(db_session)
    today = date(2026, 5, 1)
    repo.upsert_batch([
        _make_record(ticker="NVDA", earnings_date=date(2026, 5, 28)),
        _make_record(ticker="NVDA", earnings_date=date(2026, 8, 27)),
    ])

    result = repo.get_next_earnings("NVDA", today)
    assert result is not None
    assert result.earnings_date == date(2026, 5, 28)


# ─────────────────── 标准 8: get_next_earnings 无记录 ───────────────────────

def test_get_next_earnings_returns_none_when_no_future_records(db_session):
    """标准 8: 无未来记录时返回 None."""
    repo = EarningsEventRepository(db_session)
    # 只插入过去的记录
    repo.upsert_batch([_make_record(ticker="MSFT", earnings_date=date(2026, 1, 15))])

    result = repo.get_next_earnings("MSFT", date(2026, 5, 1))
    assert result is None


# ─────────────────── 标准 9: FakeFMP 调用验证 ───────────────────────────────

def test_fmp_get_earnings_calendar_called_with_correct_params(fake_fmp):
    """标准 9: FakeFMP.get_earnings_calendar 被调用，传入正确 from/to 参数."""
    fake_fmp.earnings_calendar_result = []
    today = date(2026, 5, 1)
    from_expected = (today - timedelta(days=7)).isoformat()   # 2026-04-24
    to_expected = (today + timedelta(days=30)).isoformat()    # 2026-05-31

    from app.services.cockpit.earnings_service import EarningsService
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with Session() as db:
        svc = EarningsService(db, fake_fmp)
        svc.fetch_and_store(today=today)

    assert len(fake_fmp.earnings_calendar_calls) == 1
    call_from, call_to = fake_fmp.earnings_calendar_calls[0]
    assert call_from == from_expected
    assert call_to == to_expected


# ─────────────────── 标准 10: fetch_and_store 写入 DB ───────────────────────

def test_fetch_and_store_writes_records_to_db(db_session, fake_fmp):
    """标准 10: fetch_and_store 以 FakeFMP 注入，3 条 FMP 记录 → DB 写入 3 行."""
    fake_fmp.earnings_calendar_result = [
        _make_fmp_item("AAPL", "2026-05-22", eps_estimated=1.5),
        _make_fmp_item("NVDA", "2026-05-28", eps_estimated=5.2),
        _make_fmp_item("MSFT", "2026-07-30", eps_estimated=3.1),
    ]

    svc = EarningsService(db_session, fake_fmp)
    result = svc.fetch_and_store(today=date(2026, 4, 24))

    assert result["fetched"] == 3
    assert result["upserted"] == 3
    assert db_session.query(EarningsEvent).count() == 3


def test_fetch_and_store_normalizes_time_of_day(db_session, fake_fmp):
    """时间字段：BMO/AMC 保留，'--' 和其他映射为 None."""
    fake_fmp.earnings_calendar_result = [
        _make_fmp_item("A", "2026-05-01", time="BMO"),
        _make_fmp_item("B", "2026-05-02", time="AMC"),
        _make_fmp_item("C", "2026-05-03", time="--"),
        _make_fmp_item("D", "2026-05-04", time=""),
    ]

    svc = EarningsService(db_session, fake_fmp)
    svc.fetch_and_store(today=date(2026, 4, 24))

    rows = {
        r.ticker: r
        for r in db_session.query(EarningsEvent).all()
    }
    assert rows["A"].time_of_day == "BMO"
    assert rows["B"].time_of_day == "AMC"
    assert rows["C"].time_of_day is None
    assert rows["D"].time_of_day is None


# ─────────────────── 标准 11: get_next_earnings dict 字段 ───────────────────

def test_get_next_earnings_returns_camelcase_dict(db_session, fake_fmp):
    """标准 11: get_next_earnings 返回 dict，键名 camelCase 与 API-CONTRACT 对齐."""
    fake_fmp.earnings_calendar_result = [
        _make_fmp_item("TSLA", "2026-05-20", eps_estimated=0.72, time="AMC"),
    ]

    svc = EarningsService(db_session, fake_fmp)
    svc.fetch_and_store(today=date(2026, 4, 24))

    result = svc.get_next_earnings("TSLA")

    assert result["ticker"] == "TSLA"
    assert result["nextEarningsDate"] == "2026-05-20"
    assert isinstance(result["daysUntil"], int)
    assert result["timeOfDay"] == "AMC"
    assert result["epsEstimate"] == pytest.approx(0.72)
    assert "revenueEstimate" in result


def test_get_next_earnings_returns_none_fields_when_no_record(db_session, fake_fmp):
    """get_next_earnings 无记录时所有日期字段为 None."""
    svc = EarningsService(db_session, fake_fmp)
    result = svc.get_next_earnings("UNKNOWN")

    assert result["ticker"] == "UNKNOWN"
    assert result["nextEarningsDate"] is None
    assert result["daysUntil"] is None
    assert result["timeOfDay"] is None
