from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import inspect

from app.models.market_breakout_scan import MarketBreakoutScan
from app.models.market_scan_universe import MarketScanUniverse
from app.repositories.market_breakout_repository import (
    BreakoutScanRow,
    MarketBreakoutRepository,
)
from app.repositories.market_scan_universe_repository import (
    MarketScanUniverseRepository,
    UniverseUpsertRow,
)


# ---------------------------------------------------------------------------
# Schema checks (DATA-MODEL.md 对齐)
# ---------------------------------------------------------------------------


def test_schema_market_scan_universe_columns(session_engine):
    cols = {c["name"]: c for c in inspect(session_engine).get_columns("market_scan_universe")}
    assert set(cols.keys()) == {
        "id",
        "ticker",
        "company_name",
        "exchange",
        "market_cap",
        "last_seen_at",
        "added_at",
    }
    indexes = inspect(session_engine).get_indexes("market_scan_universe")
    ticker_idx = [ix for ix in indexes if ix["column_names"] == ["ticker"]]
    assert ticker_idx and ticker_idx[0]["unique"]


def test_schema_market_breakout_scans_columns(session_engine):
    cols = {
        c["name"]: c for c in inspect(session_engine).get_columns("market_breakout_scans")
    }
    assert set(cols.keys()) == {
        "id",
        "scan_date",
        "ticker",
        "company_name",
        "signal_type",
        "close_price",
        "ma150_value",
        "pct_above_ma150",
        "slope_value",
        "volume",
        "volume_ratio_20",
        "market_cap",
        "scanned_at",
    }
    uniques = inspect(session_engine).get_unique_constraints("market_breakout_scans")
    assert any(
        set(u["column_names"]) == {"scan_date", "ticker", "signal_type"}
        and u["name"] == "uq_breakout_scan_date_ticker_signal"
        for u in uniques
    )


# ---------------------------------------------------------------------------
# MarketScanUniverseRepository
# ---------------------------------------------------------------------------


def _u(ticker: str, cap: int = 60_000_000_000, name: str | None = None) -> UniverseUpsertRow:
    return UniverseUpsertRow(
        ticker=ticker,
        company_name=name or f"{ticker} Inc.",
        exchange="NASDAQ",
        market_cap=cap,
    )


def test_universe_upsert_inserts_then_updates_preserving_added_at(db_session):
    repo = MarketScanUniverseRepository(db_session)
    t0 = datetime(2026, 4, 1, 5, 0)
    t1 = datetime(2026, 5, 1, 5, 0)

    assert repo.upsert_many([_u("AAPL", 3_000_000_000_000)], now=t0) == 1
    assert repo.count() == 1

    row_after_first = db_session.execute(
        MarketScanUniverse.__table__.select()
    ).mappings().first()
    assert row_after_first["added_at"] == t0
    assert row_after_first["last_seen_at"] == t0
    assert row_after_first["market_cap"] == 3_000_000_000_000

    # 第二次同 ticker：更新市值，但 added_at 保留
    repo.upsert_many([_u("AAPL", 3_100_000_000_000, name="Apple Inc. v2")], now=t1)
    assert repo.count() == 1  # 行数不变

    row_after_second = db_session.execute(
        MarketScanUniverse.__table__.select()
    ).mappings().first()
    assert row_after_second["added_at"] == t0  # 保留首次
    assert row_after_second["last_seen_at"] == t1
    assert row_after_second["market_cap"] == 3_100_000_000_000
    assert row_after_second["company_name"] == "Apple Inc. v2"


def test_universe_list_active_filters_by_since(db_session):
    repo = MarketScanUniverseRepository(db_session)
    t_old = datetime(2026, 3, 1)
    t_new = datetime(2026, 4, 1)

    repo.upsert_many([_u("OLD1"), _u("OLD2")], now=t_old)
    repo.upsert_many([_u("NEW1"), _u("NEW2")], now=t_new)

    active = repo.list_active(since=t_new)
    assert [r.ticker for r in active] == ["NEW1", "NEW2"]


def test_universe_latest_refresh_time_and_count(db_session):
    repo = MarketScanUniverseRepository(db_session)
    assert repo.count() == 0
    assert repo.latest_refresh_time() is None

    t = datetime(2026, 4, 1)
    repo.upsert_many([_u("AAA"), _u("BBB")], now=t)

    assert repo.count() == 2
    assert repo.latest_refresh_time() == t


# ---------------------------------------------------------------------------
# MarketBreakoutRepository
# ---------------------------------------------------------------------------


def _b(
    ticker: str,
    pct: float,
    scan_date: date = date(2026, 4, 20),
    scanned_at: datetime | None = None,
    signal_type: str = "legacy_crossover",
) -> BreakoutScanRow:
    return BreakoutScanRow(
        scan_date=scan_date,
        ticker=ticker,
        company_name=f"{ticker} Corp",
        signal_type=signal_type,
        close_price=100.0 * (1 + pct / 100),
        ma150_value=100.0,
        pct_above_ma150=pct,
        slope_value=0.25,
        market_cap=80_000_000_000,
        scanned_at=scanned_at or datetime(2026, 4, 20, 22, 15),
    )


def test_replace_scan_overwrites_previous_snapshot(db_session):
    repo = MarketBreakoutRepository(db_session)

    assert repo.replace_scan([_b("A", 1.0), _b("B", 2.0), _b("C", 3.0)]) == 3
    assert db_session.query(MarketBreakoutScan).count() == 3

    # 第二次扫描（不同日），只 2 行 → 旧 3 行被清空
    later = datetime(2026, 4, 21, 22, 15)
    assert (
        repo.replace_scan(
            [
                _b("X", 0.5, scan_date=date(2026, 4, 21), scanned_at=later),
                _b("Y", 1.5, scan_date=date(2026, 4, 21), scanned_at=later),
            ]
        )
        == 2
    )
    rows = db_session.query(MarketBreakoutScan).all()
    assert len(rows) == 2
    assert {r.ticker for r in rows} == {"X", "Y"}


def test_replace_scan_atomic_on_mid_transaction_failure(db_session):
    repo = MarketBreakoutRepository(db_session)

    # 第一次写入 3 行
    repo.replace_scan([_b("A", 1.0), _b("B", 2.0), _b("C", 3.0)])
    assert db_session.query(MarketBreakoutScan).count() == 3

    # 构造一批会在 INSERT 阶段因为 UniqueConstraint 冲突而抛异常的 rows：
    # 同 batch 内两条 (scan_date, ticker) 重复。DELETE 已执行，INSERT 失败。
    # 单事务语义要求回滚到写入前状态（3 行仍在）。
    dup_day = date(2026, 4, 22)
    dup_scanned_at = datetime(2026, 4, 22, 22, 15)
    bad_rows = [
        _b("DUP", 0.1, scan_date=dup_day, scanned_at=dup_scanned_at),
        _b("DUP", 0.2, scan_date=dup_day, scanned_at=dup_scanned_at),
    ]

    with pytest.raises(Exception):
        repo.replace_scan(bad_rows)

    # session 因异常处于无效事务状态，显式回滚后读取
    db_session.rollback()
    remaining = db_session.query(MarketBreakoutScan).all()
    assert len(remaining) == 3
    assert {r.ticker for r in remaining} == {"A", "B", "C"}


def test_get_latest_snapshot_orders_ascending_and_handles_empty(db_session):
    repo = MarketBreakoutRepository(db_session)
    assert repo.get_latest_snapshot() is None

    # 旧 scan
    old_day = date(2026, 4, 19)
    old_ts = datetime(2026, 4, 19, 22, 15)
    # 新 scan（更高 scanned_at）
    new_day = date(2026, 4, 20)
    new_ts = datetime(2026, 4, 20, 22, 15)

    # 先写旧
    repo.replace_scan(
        [
            _b("OLD1", 1.0, scan_date=old_day, scanned_at=old_ts),
            _b("OLD2", 2.0, scan_date=old_day, scanned_at=old_ts),
        ]
    )
    # 再写新（replace → 旧被清）
    repo.replace_scan(
        [
            _b("HIGH", 8.5, scan_date=new_day, scanned_at=new_ts),
            _b("LOW", 0.3, scan_date=new_day, scanned_at=new_ts),
            _b("MID", 4.2, scan_date=new_day, scanned_at=new_ts),
        ]
    )

    snap = repo.get_latest_snapshot()
    assert snap is not None
    assert snap.scan_date == new_day
    assert snap.scanned_at == new_ts
    assert [i.ticker for i in snap.items] == ["LOW", "MID", "HIGH"]


def test_replace_scan_empty_input_clears_table(db_session):
    repo = MarketBreakoutRepository(db_session)
    repo.replace_scan([_b("A", 1.0)])
    assert db_session.query(MarketBreakoutScan).count() == 1

    # 零命中也是合法快照：清空旧数据
    assert repo.replace_scan([]) == 0
    assert db_session.query(MarketBreakoutScan).count() == 0
    assert repo.get_latest_snapshot() is None
