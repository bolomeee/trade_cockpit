"""F218-d2 tests — T1 EARNINGS_ACCEL detector (repo new method + detector logic + end-to-end).

10 tests grouped into 3 classes:
  TestEarningsEventRepoRecentCompleted  — E1–E2  (repo new method)
  TestDetectEarningsAcceleration        — D3–D9  (detector unit tests, D5 & D9 parametrized)
  TestEarningsAccelEndToEnd             — T10    (compute_and_store_all_triggers integration)
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Stock
from app.models.earnings_event import EarningsEvent
from app.models.repricing_trigger import RepricingTrigger
from app.repositories.earnings_event_repository import EarningsEventRepository
from app.services.cockpit.repricing_trigger_service import (
    RepricingTriggerService,
    _quarter_label,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _ee(
    db: Session,
    *,
    ticker: str = "AAPL",
    earnings_date: date,
    eps_actual: float | None = None,
    revenue_actual: int | None = None,
) -> EarningsEvent:
    row = EarningsEvent(
        ticker=ticker,
        earnings_date=earnings_date,
        eps_actual=eps_actual,
        revenue_actual=revenue_actual,
        fetched_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _stock(db: Session, ticker: str = "AAPL") -> Stock:
    row = Stock(
        ticker=ticker,
        name=f"{ticker} Inc",
        exchange="NASDAQ",
        is_active=True,
        added_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _insert_6_seasons(
    db: Session,
    ticker: str = "AAPL",
    eps_actuals: list[float] | None = None,
    revenue_actuals: list[int | None] | None = None,
) -> None:
    """Insert 6 completed earnings rows (DESC date order = index 0 is most recent).

    Default EPS yields strictly monotone YoY: [0.10, 0.15, 0.20] < 0.30% threshold → confidence=0.5.
    Dates are aligned so rows[0..2] pair with rows[3..5] as YoY counterparts.
    """
    if eps_actuals is None:
        eps_actuals = [1.10, 1.05, 1.00, 1.00, 1.00, 1.00]
    if revenue_actuals is None:
        revenue_actuals = [1100, 1050, 1000, 1000, 1000, 1000]

    # rows[0] = most recent (2026-02-15), rows[3] = prior year (2025-02-15), etc.
    dates = [
        date(2026, 2, 15),
        date(2025, 11, 15),
        date(2025, 8, 15),
        date(2025, 2, 15),
        date(2024, 11, 15),
        date(2024, 8, 15),
    ]
    for i, (d, eps, rev) in enumerate(zip(dates, eps_actuals, revenue_actuals)):
        _ee(db, ticker=ticker, earnings_date=d, eps_actual=eps, revenue_actual=rev)


# ── Class 1: Repo new method ──────────────────────────────────────────────────


class TestEarningsEventRepoRecentCompleted:

    def test_e1_returns_only_actual_rows_desc_limit(self, db_session: Session) -> None:
        """Only eps_actual IS NOT NULL rows returned, ordered DESC, limited correctly."""
        # 6 rows with eps_actual, 2 without
        dates_with = [date(2026, i, 15) for i in range(1, 7)]
        dates_without = [date(2026, 7, 15), date(2026, 8, 15)]
        for d in dates_with:
            _ee(db_session, earnings_date=d, eps_actual=1.0)
        for d in dates_without:
            _ee(db_session, earnings_date=d, eps_actual=None)

        repo = EarningsEventRepository(db_session)
        results = repo.get_recent_completed_for_ticker("AAPL", limit=8)

        assert len(results) == 6
        assert all(r.eps_actual is not None for r in results)
        # DESC order
        for i in range(len(results) - 1):
            assert results[i].earnings_date > results[i + 1].earnings_date

        # limit=3 truncates
        r3 = repo.get_recent_completed_for_ticker("AAPL", limit=3)
        assert len(r3) == 3

    def test_e2_empty_when_no_actual_rows(self, db_session: Session) -> None:
        """Returns empty list (not error) when ticker has no completed earnings."""
        _ee(db_session, ticker="AAPL", earnings_date=date(2026, 1, 15), eps_actual=None)

        repo = EarningsEventRepository(db_session)
        assert repo.get_recent_completed_for_ticker("AAPL") == []
        assert repo.get_recent_completed_for_ticker("UNKNOWN") == []


# ── Class 2: Detector unit tests ─────────────────────────────────────────────


class TestDetectEarningsAcceleration:

    def test_d3_hit_confidence_low(self, db_session: Session) -> None:
        """6 seasons complete + strictly monotone YoY + recent YoY < 30% → DetectorResult(0.5)."""
        # eps_actuals DESC: [1.10, 1.05, 1.00, 1.00, 1.00, 1.00]
        # YoY DESC (before reverse): [0.10, 0.05, 0.00] → reversed → [0.00, 0.05, 0.10]
        # strictly monotone 0.00 < 0.05 < 0.10 ✓; latest yoy=0.10 < 0.30 → confidence=0.5
        # Also add revenue to check revenue_yoy_growth filled
        _insert_6_seasons(
            db_session,
            eps_actuals=[1.10, 1.05, 1.00, 1.00, 1.00, 1.00],
            revenue_actuals=[1100, 1050, 1000, 1000, 1000, 1000],
        )
        _stock(db_session)
        svc = RepricingTriggerService(db_session)
        result = svc._detect_earnings_acceleration("AAPL", date(2026, 3, 1))

        assert result is not None
        assert result.confidence == pytest.approx(0.5)
        ev = result.evidence
        assert len(ev["eps_yoy_growth"]) == 3
        assert len(ev["revenue_yoy_growth"]) == 3
        assert len(ev["quarters"]) == 3
        # eps_yoy in time order [Q-3, Q-2, Q-1]: strictly increasing
        yoy = ev["eps_yoy_growth"]
        assert yoy[0] < yoy[1] < yoy[2]

    def test_d4_hit_confidence_high(self, db_session: Session) -> None:
        """Recent YoY ≥ 30% → confidence=0.8."""
        # eps DESC: [2.00, 1.40, 1.10, 1.00, 1.00, 1.00]
        # YoY DESC (before reverse): [1.00, 0.40, 0.10] → reversed → [0.10, 0.40, 1.00]
        # strictly monotone ✓; latest=1.00 ≥ 0.30 → confidence=0.8
        _insert_6_seasons(
            db_session,
            eps_actuals=[2.00, 1.40, 1.10, 1.00, 1.00, 1.00],
            revenue_actuals=[2000, 1400, 1100, 1000, 1000, 1000],
        )
        _stock(db_session)
        svc = RepricingTriggerService(db_session)
        result = svc._detect_earnings_acceleration("AAPL", date(2026, 3, 1))

        assert result is not None
        assert result.confidence == pytest.approx(0.8)

    @pytest.mark.parametrize(
        "eps_actuals, label",
        [
            # case 1: flat (持平) — [0.10, 0.10, 0.20] not strictly < at [0] == [1]
            ([1.10, 1.10, 1.10, 1.00, 1.00, 1.00], "flat"),
            # case 2: declining — rows DESC [1.20,1.25,1.30,1.00,1.00,1.00] → yoy reversed [0.30,0.25,0.20]
            ([1.20, 1.25, 1.30, 1.00, 1.00, 1.00], "declining"),
            # case 3: mid dip — yoy [0.10, 0.30, 0.20] not monotone (dip at end)
            ([1.10, 1.30, 1.20, 1.00, 1.00, 1.00], "mid_dip"),
        ],
    )
    def test_d5_non_monotone_returns_none(
        self, db_session: Session, eps_actuals: list[float], label: str
    ) -> None:
        """Non-strictly-monotone YoY → None (flat / declining / mid-dip)."""
        _insert_6_seasons(db_session, eps_actuals=eps_actuals)
        _stock(db_session)
        svc = RepricingTriggerService(db_session)
        result = svc._detect_earnings_acceleration("AAPL", date(2026, 3, 1))
        assert result is None, f"Expected None for {label} case"

    def test_d6_insufficient_history_returns_none(self, db_session: Session) -> None:
        """Fewer than 6 completed quarters → None."""
        # Only insert 5 rows
        for i in range(5):
            _ee(db_session, earnings_date=date(2024 + i // 4, (i % 4) * 3 + 1, 15), eps_actual=1.0 + i * 0.1)
        _stock(db_session)
        svc = RepricingTriggerService(db_session)
        result = svc._detect_earnings_acceleration("AAPL", date(2026, 3, 1))
        assert result is None

        # Also test 0 rows
        svc2 = RepricingTriggerService(db_session)
        result2 = svc2._detect_earnings_acceleration("MSFT", date(2026, 3, 1))
        assert result2 is None

    def test_d7_negative_prior_eps_returns_none(self, db_session: Session) -> None:
        """Prior year EPS ≤ 0 (zero or negative) → None (no negative-base division)."""
        # prior eps ≤ 0: rows[3].eps_actual = 0.0 triggers return None
        _insert_6_seasons(
            db_session,
            eps_actuals=[1.10, 1.05, 1.00, 0.0, 1.00, 1.00],
        )
        _stock(db_session)
        svc = RepricingTriggerService(db_session)
        result = svc._detect_earnings_acceleration("AAPL", date(2026, 3, 1))
        assert result is None

        # negative prior
        db_session.query(EarningsEvent).delete()
        db_session.commit()
        _insert_6_seasons(
            db_session,
            eps_actuals=[1.10, 1.05, 1.00, -0.5, 1.00, 1.00],
        )
        result2 = svc._detect_earnings_acceleration("AAPL", date(2026, 3, 1))
        assert result2 is None

    def test_d8_revenue_missing_still_triggers(self, db_session: Session) -> None:
        """Revenue None → still fires; revenue_yoy_growth has None at that position."""
        # Strictly monotone EPS with high confidence; revenue_actual=None on some rows
        _insert_6_seasons(
            db_session,
            eps_actuals=[2.00, 1.40, 1.10, 1.00, 1.00, 1.00],
            revenue_actuals=[None, None, None, None, None, None],
        )
        _stock(db_session)
        svc = RepricingTriggerService(db_session)
        result = svc._detect_earnings_acceleration("AAPL", date(2026, 3, 1))

        assert result is not None
        assert result.confidence == pytest.approx(0.8)
        # All revenue_yoy_growth positions are None
        assert result.evidence["revenue_yoy_growth"] == [None, None, None]

    @pytest.mark.parametrize(
        "d, expected",
        [
            (date(2026, 2, 15), "2026Q1"),
            (date(2025, 12, 31), "2025Q4"),
            (date(2025, 4, 1), "2025Q2"),
        ],
    )
    def test_d9_quarter_label(self, d: date, expected: str) -> None:
        """_quarter_label maps dates to YYYYQN correctly."""
        assert _quarter_label(d) == expected


# ── Class 3: End-to-end ───────────────────────────────────────────────────────


class TestEarningsAccelEndToEnd:

    def test_t10_hit_upserts_then_miss_soft_expires(self, db_session: Session) -> None:
        """Full pipeline: T1 hit → upsert repricing_triggers; re-scan miss → soft expire."""
        _stock(db_session, "AAPL")
        # Strictly monotone high-confidence data
        _insert_6_seasons(
            db_session,
            ticker="AAPL",
            eps_actuals=[2.00, 1.40, 1.10, 1.00, 1.00, 1.00],
            revenue_actuals=[2000, 1400, 1100, 1000, 1000, 1000],
        )

        svc = RepricingTriggerService(db_session)
        scan_date = date(2026, 3, 1)
        counts = svc.compute_and_store_all_triggers(scan_date=scan_date)

        assert counts["EARNINGS_ACCEL"] == 1

        row = db_session.execute(
            select(RepricingTrigger).where(
                RepricingTrigger.ticker == "AAPL",
                RepricingTrigger.trigger_type == "EARNINGS_ACCEL",
            )
        ).scalar_one()

        assert row.active is True
        assert row.confidence == pytest.approx(0.8)

        ev = json.loads(row.evidence_json)
        assert sorted(ev.keys()) == sorted(["eps_yoy_growth", "revenue_yoy_growth", "quarters"])
        assert len(ev["eps_yoy_growth"]) == 3
        assert len(ev["revenue_yoy_growth"]) == 3
        assert len(ev["quarters"]) == 3

        # Re-scan with non-monotone data → T1 misses → soft expire
        db_session.query(EarningsEvent).delete()
        db_session.commit()
        # Flat YoY (持平) → will return None from detector
        _insert_6_seasons(
            db_session,
            ticker="AAPL",
            eps_actuals=[1.10, 1.10, 1.10, 1.00, 1.00, 1.00],
        )

        counts2 = svc.compute_and_store_all_triggers(scan_date=date(2026, 3, 2))
        assert counts2["EARNINGS_ACCEL"] == 0

        row_after = db_session.execute(
            select(RepricingTrigger).where(
                RepricingTrigger.ticker == "AAPL",
                RepricingTrigger.trigger_type == "EARNINGS_ACCEL",
            )
        ).scalar_one()
        assert row_after.active is False
