"""F218-d6b tests — T5 BALANCE_INFLECTION detector (helpers + detector unit tests + end-to-end).

10 tests grouped into 4 classes:
  TestEvalNetDebtArm            — B1–B3  (helper unit tests, B3 parametrized ×5)
  TestEvalFcfArm                — B4–B5  (helper unit tests, B5 parametrized ×4)
  TestDetectBalanceInflection   — B6–B9  (detector unit tests, B9 parametrized ×3)
  TestBalanceInflectionEndToEnd — B10    (compute_and_store_all_triggers integration)

B11 evidence_json 4-key schema assertion is embedded inside B6.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Stock
from app.models.repricing_trigger import RepricingTrigger
from app.models.stock_fundamentals_quarterly import StockFundamentalsQuarterly
from app.services.cockpit.repricing_trigger_service import (
    RepricingTriggerService,
    _eval_fcf_arm,
    _eval_net_debt_arm,
)


# ── Shared fixtures ───────────────────────────────────────────────────────────

# 3 rows DESC by period_end_date when returned from repo:
#   rows[0]=Q0(2026Q1)  rows[1]=Q-1(2025Q4)  rows[2]=Q-2(2025Q3)
_DATES = [
    date(2026, 3, 31),   # Q0  → "2026Q1"
    date(2025, 12, 31),  # Q-1 → "2025Q4"
    date(2025, 9, 30),   # Q-2 → "2025Q3"
]
_FQ = ["Q1 2026", "Q4 2025", "Q3 2025"]


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


def _fundamentals(
    db: Session,
    *,
    ticker: str = "AAPL",
    fiscal_quarter: str,
    period_end_date: date,
    total_debt: int | None = None,
    cash: int | None = None,
    net_debt: int | None = None,
    fcf: int | None = None,
) -> StockFundamentalsQuarterly:
    """INSERT one StockFundamentalsQuarterly row directly."""
    row = StockFundamentalsQuarterly(
        ticker=ticker,
        fiscal_quarter=fiscal_quarter,
        period_end_date=period_end_date,
        total_debt=total_debt,
        cash=cash,
        net_debt=net_debt,
        fcf=fcf,
        fetched_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _insert_3_seasons_for_t5(
    db: Session,
    ticker: str = "AAPL",
    net_debt_series: list[int | None] | None = None,
    fcf_series: list[int | None] | None = None,
) -> None:
    """Insert 3 fundamentals rows (series index 0=Q-2, 1=Q-1, 2=Q0 — time-ascending).

    Default net_debt_series: [120M, 105M, 95M] → net_debt arm hits (both QoQ ≥ 5% decline).
    Default fcf_series: [None, None, None] → fcf arm skipped.
    """
    if net_debt_series is None:
        net_debt_series = [120_000_000, 105_000_000, 95_000_000]
    if fcf_series is None:
        fcf_series = [None, None, None]

    # _DATES[0]=Q0 (most recent), _DATES[1]=Q-1, _DATES[2]=Q-2 (oldest)
    # net_debt_series[0]=Q-2 value → maps to i=2; series[2]=Q0 value → maps to i=0
    for i in range(3):
        _fundamentals(
            db,
            ticker=ticker,
            fiscal_quarter=_FQ[i],
            period_end_date=_DATES[i],
            net_debt=net_debt_series[2 - i],
            fcf=fcf_series[2 - i],
        )


# ── Class 1: _eval_net_debt_arm unit tests ────────────────────────────────────


class TestEvalNetDebtArm:

    def test_b1_happy_both_qoq_pass(self) -> None:
        """Both QoQ ≥ 5% decline → (True, recent_qoq_pct).

        net_debt [Q-2, Q-1, Q0] = [120M, 105M, 95M]:
          QoQ_recent = (105M−95M)/105M ≈ 9.52% ≥ 5% ✓
          QoQ_prior  = (120M−105M)/120M ≈ 12.5% ≥ 5% ✓
        """
        hit, pct = _eval_net_debt_arm(
            95_000_000, 105_000_000, 120_000_000, threshold=0.05,
        )
        assert hit is True
        assert pct == pytest.approx(0.0952, abs=1e-3)

    def test_b2_single_qoq_below_threshold_no_hit(self) -> None:
        """Recent QoQ only ≈ 2.86% < 5% → (False, recent_qoq_pct); pct still returned.

        net_debt [Q-2, Q-1, Q0] = [120M, 105M, 102M]:
          QoQ_recent = (105M−102M)/105M ≈ 2.86% < 5% ✗
        """
        hit, pct = _eval_net_debt_arm(
            102_000_000, 105_000_000, 120_000_000, threshold=0.05,
        )
        assert hit is False
        assert pct == pytest.approx(0.0286, abs=1e-3)

    @pytest.mark.parametrize(
        "q0, q1, q2",
        [
            (None, 105_000_000, 120_000_000),   # q0 None
            (95_000_000, None, 120_000_000),    # q1 None
            (95_000_000, 105_000_000, None),    # q2 None
            (95_000_000, 0, 120_000_000),       # q1=0 → denominator ≤ 0
            (95_000_000, 105_000_000, -5),      # q2=-5 → denominator ≤ 0
        ],
    )
    def test_b3_invalid_inputs_return_false_zero(
        self, q0: int | None, q1: int | None, q2: int | None,
    ) -> None:
        """Any None / denominator ≤ 0 → (False, 0.0); no ZeroDivisionError / TypeError."""
        hit, pct = _eval_net_debt_arm(q0, q1, q2, threshold=0.05)
        assert hit is False
        assert pct == pytest.approx(0.0)


# ── Class 2: _eval_fcf_arm unit tests ────────────────────────────────────────


class TestEvalFcfArm:

    def test_b4_happy_strict_switch(self) -> None:
        """Q-2 ≤ 0, Q-1 > 0, Q0 > 0 → True (strict negative-to-positive switch)."""
        assert _eval_fcf_arm(22_000_000, 8_000_000, -15_000_000) is True

    @pytest.mark.parametrize(
        "q0, q1, q2",
        [
            (22_000_000, 8_000_000, 5_000_000),   # Q-2 > 0, no switch
            (22_000_000, -3_000_000, -15_000_000), # Q-1 ≤ 0, not yet positive
            (0, 8_000_000, -15_000_000),           # Q0 = 0, not strictly positive
            (22_000_000, None, -15_000_000),        # any None → False
        ],
    )
    def test_b5_no_switch_cases(
        self, q0: int | None, q1: int | None, q2: int | None,
    ) -> None:
        """Various non-switch conditions → False; no TypeError."""
        assert _eval_fcf_arm(q0, q1, q2) is False


# ── Class 3: _detect_balance_inflection unit tests ───────────────────────────


class TestDetectBalanceInflection:

    def test_b6_net_debt_arm_only_hit_and_evidence_schema(
        self, db_session: Session,
    ) -> None:
        """Net debt arm hits, fcf all None → trigger_metric=net_debt; B11: 4-key schema.

        net_debt=[120M, 105M, 95M] (Q-2→Q0, time ascending):
          QoQ_recent ≈ 9.52% ≥ 5% ✓  QoQ_prior ≈ 12.5% ≥ 5% ✓
        fcf all None → fcf arm skipped.
        """
        _insert_3_seasons_for_t5(db_session)
        svc = RepricingTriggerService(db_session)
        result = svc._detect_balance_inflection("AAPL", date(2026, 4, 1))

        assert result is not None
        assert result.confidence == pytest.approx(0.5)

        ev = result.evidence

        # B11: 4-key evidence_json schema
        assert set(ev.keys()) == {"net_debt_trend", "fcf_trend", "quarters", "trigger_metric"}
        assert len(ev["net_debt_trend"]) == 3
        assert len(ev["fcf_trend"]) == 3
        assert len(ev["quarters"]) == 3
        assert ev["trigger_metric"] in {"net_debt", "fcf"}

        # Specific values
        assert ev["trigger_metric"] == "net_debt"
        assert ev["net_debt_trend"] == [120_000_000, 105_000_000, 95_000_000]  # [Q-2, Q-1, Q0]
        assert ev["fcf_trend"] == [None, None, None]
        assert ev["quarters"] == ["2025Q3", "2025Q4", "2026Q1"]

    def test_b7_fcf_arm_only_hit(self, db_session: Session) -> None:
        """FCF arm hits, net_debt flat → trigger_metric=fcf.

        net_debt all 100M → QoQ=0% < 5% → net_debt arm misses.
        fcf=[-15M, 8M, 22M] (Q-2→Q0) → strict switch → fcf arm hits.
        """
        _insert_3_seasons_for_t5(
            db_session,
            net_debt_series=[100_000_000, 100_000_000, 100_000_000],
            fcf_series=[-15_000_000, 8_000_000, 22_000_000],
        )
        svc = RepricingTriggerService(db_session)
        result = svc._detect_balance_inflection("AAPL", date(2026, 4, 1))

        assert result is not None
        assert result.confidence == pytest.approx(0.5)
        assert result.evidence["trigger_metric"] == "fcf"
        assert result.evidence["net_debt_trend"] == [100_000_000, 100_000_000, 100_000_000]
        assert result.evidence["fcf_trend"] == [-15_000_000, 8_000_000, 22_000_000]

    def test_b8_both_arms_hit_net_debt_preferred(self, db_session: Session) -> None:
        """Both arms hit → trigger_metric=net_debt (DATA-MODEL §1100 偏好)."""
        _insert_3_seasons_for_t5(
            db_session,
            net_debt_series=[120_000_000, 105_000_000, 95_000_000],
            fcf_series=[-15_000_000, 8_000_000, 22_000_000],
        )
        svc = RepricingTriggerService(db_session)
        result = svc._detect_balance_inflection("AAPL", date(2026, 4, 1))

        assert result is not None
        assert result.evidence["trigger_metric"] == "net_debt"

    @pytest.mark.parametrize(
        "n_rows, net_debt_series, fcf_series, label",
        [
            # (a) fewer than 3 rows → insufficient history
            (2, [105_000_000, 95_000_000], [None, None], "insufficient_rows"),
            # (b) 3 rows, both QoQ < 5% + fcf not switching
            (3, [120_000_000, 115_000_000, 112_000_000], [5_000_000, 8_000_000, 22_000_000], "no_arm_hits"),
            # (c) 3 rows, net_debt and fcf both all None → both arms skip
            (3, [None, None, None], [None, None, None], "all_null_fields"),
        ],
    )
    def test_b9_return_none_scenarios(
        self,
        db_session: Session,
        n_rows: int,
        net_debt_series: list[int | None],
        fcf_series: list[int | None],
        label: str,
    ) -> None:
        """Various data conditions that produce return None."""
        if n_rows < 3:
            for i in range(n_rows):
                _fundamentals(
                    db_session,
                    fiscal_quarter=_FQ[i],
                    period_end_date=_DATES[i],
                    net_debt=net_debt_series[i],
                    fcf=fcf_series[i],
                )
        else:
            _insert_3_seasons_for_t5(
                db_session,
                net_debt_series=net_debt_series,
                fcf_series=fcf_series,
            )

        svc = RepricingTriggerService(db_session)
        result = svc._detect_balance_inflection("AAPL", date(2026, 4, 1))
        assert result is None, f"Expected None for scenario: {label}"


# ── Class 4: End-to-end ───────────────────────────────────────────────────────


class TestBalanceInflectionEndToEnd:

    def test_b10_hit_upserts_then_miss_soft_expires(self, db_session: Session) -> None:
        """Full pipeline: T5 hit → upsert repricing_triggers; re-scan miss → soft expire."""
        _stock(db_session, "AAPL")
        _insert_3_seasons_for_t5(db_session, ticker="AAPL")

        svc = RepricingTriggerService(db_session)
        scan_date = date(2026, 4, 1)
        counts = svc.compute_and_store_all_triggers(scan_date=scan_date)

        assert counts["BALANCE_INFLECTION"] == 1

        row = db_session.execute(
            select(RepricingTrigger).where(
                RepricingTrigger.ticker == "AAPL",
                RepricingTrigger.trigger_type == "BALANCE_INFLECTION",
            )
        ).scalar_one()

        assert row.active is True
        assert row.confidence == pytest.approx(0.5)

        ev = json.loads(row.evidence_json)
        assert set(ev.keys()) == {"net_debt_trend", "fcf_trend", "quarters", "trigger_metric"}
        assert ev["trigger_metric"] == "net_debt"
        assert len(ev["net_debt_trend"]) == 3
        assert len(ev["fcf_trend"]) == 3
        assert len(ev["quarters"]) == 3

        # Re-scan: flatten Q0.net_debt to 102M → QoQ_recent ≈ 2.86% < 5% → miss → soft expire
        q0_row = db_session.execute(
            select(StockFundamentalsQuarterly).where(
                StockFundamentalsQuarterly.ticker == "AAPL",
                StockFundamentalsQuarterly.period_end_date == _DATES[0],
            )
        ).scalar_one()
        q0_row.net_debt = 102_000_000
        db_session.commit()

        counts2 = svc.compute_and_store_all_triggers(scan_date=date(2026, 4, 2))
        assert counts2["BALANCE_INFLECTION"] == 0

        db_session.expire_all()
        row_after = db_session.execute(
            select(RepricingTrigger).where(
                RepricingTrigger.ticker == "AAPL",
                RepricingTrigger.trigger_type == "BALANCE_INFLECTION",
            )
        ).scalar_one()
        assert row_after.active is False
