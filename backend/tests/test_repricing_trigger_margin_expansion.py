"""F218-d3b tests — T2 MARGIN_EXPANSION detector (helpers + detector unit tests + end-to-end).

10 tests grouped into 3 classes:
  TestEvalMarginArm           — M1–M3  (helper unit tests, M3 parametrized ×4)
  TestDetectMarginExpansion   — M4–M9  (detector unit tests, M9 parametrized ×3)
  TestMarginExpansionEndToEnd — M10    (compute_and_store_all_triggers integration)

M11 evidence_json 5-key schema assertion is embedded inside M4.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Stock
from app.models.repricing_trigger import RepricingTrigger
from app.models.stock_key_metrics_quarterly import StockKeyMetricsQuarterly
from app.services.cockpit.repricing_trigger_service import (
    RepricingTriggerService,
    _eval_margin_arm,
    _round_or_none,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

# 6 rows DESC by period_end_date:
#   rows[0]=Q0(2026Q1) rows[1]=Q-1(2025Q4) rows[2]=Q-2(2025Q3)
#   rows[3]=Q-3(2025Q2) rows[4]=Q-4(2025Q1) rows[5]=Q-5(2024Q4)
_DATES = [
    date(2026, 3, 31),   # Q0  → "2026Q1"
    date(2025, 12, 31),  # Q-1 → "2025Q4"
    date(2025, 9, 30),   # Q-2 → "2025Q3"
    date(2025, 6, 30),   # Q-3 → "2025Q2"
    date(2025, 3, 31),   # Q-4 → "2025Q1"
    date(2024, 12, 31),  # Q-5 → "2024Q4"
]
_FQ = ["Q1 2026", "Q4 2025", "Q3 2025", "Q2 2025", "Q1 2025", "Q4 2024"]


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


def _km(
    db: Session,
    *,
    ticker: str = "AAPL",
    fiscal_quarter: str,
    period_end_date: date,
    gross_margin: float | None = None,
    fcf_margin: float | None = None,
) -> StockKeyMetricsQuarterly:
    """INSERT one StockKeyMetricsQuarterly row directly."""
    row = StockKeyMetricsQuarterly(
        ticker=ticker,
        fiscal_quarter=fiscal_quarter,
        period_end_date=period_end_date,
        gross_margin=gross_margin,
        fcf_margin=fcf_margin,
        fetched_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _insert_6_seasons_for_t2(
    db: Session,
    ticker: str = "AAPL",
    gross_series: list[float | None] | None = None,
    fcf_series: list[float | None] | None = None,
) -> None:
    """Insert 6 key_metrics rows (index 0 = Q0 most recent, 5 = Q-5 oldest).

    Default gross_series yields low-confidence gross arm hit:
      [0.42, 0.41, 0.41, 0.40, 0.40, 0.38] → Q0 YoY=200bp, Q-1 YoY=300bp → confidence=0.5.
    Default fcf_series: all None (d6a not yet integrated).
    """
    if gross_series is None:
        gross_series = [0.42, 0.41, 0.41, 0.40, 0.40, 0.38]
    if fcf_series is None:
        fcf_series = [None] * 6

    for i in range(6):
        _km(
            db,
            ticker=ticker,
            fiscal_quarter=_FQ[i],
            period_end_date=_DATES[i],
            gross_margin=gross_series[i],
            fcf_margin=fcf_series[i],
        )


# ── Class 1: _eval_margin_arm unit tests ─────────────────────────────────────


class TestEvalMarginArm:

    def test_m1_happy_both_yoy_pass(self) -> None:
        """Both Q0 vs Q-4 and Q-1 vs Q-5 ≥ threshold → (True, q0_bp)."""
        # Q0 YoY = round((0.46-0.42)*10000) = 400bp ≥ 200 ✓
        # Q-1 YoY = round((0.44-0.40)*10000) = 400bp ≥ 200 ✓
        hit, q0_bp = _eval_margin_arm(0.46, 0.44, 0.42, 0.40, threshold_bp=200)
        assert hit is True
        assert q0_bp == 400

    def test_m2_q0_yoy_below_threshold_no_hit(self) -> None:
        """Q0 YoY < threshold → (False, q0_bp); q0_bp still calculated for debugging."""
        # Q0 YoY = round((0.43-0.42)*10000) = 100bp < 200 → no hit
        # Q-1 YoY = round((0.44-0.40)*10000) = 400bp ≥ 200, but q0 fails first condition
        hit, q0_bp = _eval_margin_arm(0.43, 0.44, 0.42, 0.40, threshold_bp=200)
        assert hit is False
        assert q0_bp == 100

    @pytest.mark.parametrize(
        "q0, q1, q4, q5",
        [
            (None, 0.44, 0.42, 0.40),  # q0 None
            (0.46, None, 0.42, 0.40),  # q1 None
            (0.46, 0.44, None, 0.40),  # q4 None
            (0.46, 0.44, 0.42, None),  # q5 None
        ],
    )
    def test_m3_any_none_field_returns_false_zero(
        self,
        q0: float | None,
        q1: float | None,
        q4: float | None,
        q5: float | None,
    ) -> None:
        """Any None input field → (False, 0); no TypeError raised."""
        hit, q0_bp = _eval_margin_arm(q0, q1, q4, q5, threshold_bp=200)
        assert hit is False
        assert q0_bp == 0


# ── Class 2: _detect_margin_expansion unit tests ──────────────────────────────


class TestDetectMarginExpansion:

    def test_m4_gross_hit_low_confidence_and_evidence_schema(
        self, db_session: Session,
    ) -> None:
        """Gross arm hit, Q0 YoY < 400bp → confidence=0.5; M11: evidence_json 5-key schema.

        gross [Q0..Q-5] = [0.42, 0.41, 0.41, 0.40, 0.40, 0.38]
          Q0 YoY = (0.42-0.40)*10000 = 200bp ≥ 200 ✓
          Q-1 YoY = (0.41-0.38)*10000 = 300bp ≥ 200 ✓
          expansion_bp = 200 < 400 → confidence = 0.5
        """
        _insert_6_seasons_for_t2(db_session)
        svc = RepricingTriggerService(db_session)
        result = svc._detect_margin_expansion("AAPL", date(2026, 4, 1))

        assert result is not None
        assert result.confidence == pytest.approx(0.5)

        ev = result.evidence

        # M11: 5-key evidence_json schema
        assert set(ev.keys()) == {
            "gross_margin_trend", "fcf_margin_trend", "quarters",
            "trigger_metric", "expansion_bp",
        }
        assert len(ev["gross_margin_trend"]) == 3
        assert len(ev["fcf_margin_trend"]) == 3
        assert len(ev["quarters"]) == 3
        assert ev["trigger_metric"] in {"gross_margin", "fcf_margin"}

        # Specific values
        assert ev["trigger_metric"] == "gross_margin"
        assert ev["expansion_bp"] == 200             # int, not float
        assert isinstance(ev["expansion_bp"], int)

        # trend [Q-2, Q-1, Q0]: rows[2].gross=0.41, rows[1].gross=0.41, rows[0].gross=0.42
        assert ev["gross_margin_trend"] == pytest.approx([0.41, 0.41, 0.42])

        # d3b: fcf all None → trend all null
        assert ev["fcf_margin_trend"] == [None, None, None]

        # quarters [Q-2, Q-1, Q0] = ["2025Q3", "2025Q4", "2026Q1"]
        assert ev["quarters"] == ["2025Q3", "2025Q4", "2026Q1"]

    def test_m5_gross_high_confidence(self, db_session: Session) -> None:
        """Gross arm hit with Q0 YoY ≥ 400bp → confidence=0.8."""
        # gross [Q0..Q-5] = [0.46, 0.44, 0.43, 0.42, 0.42, 0.40]
        # Q0 YoY = (0.46-0.42)*10000 = 400bp ≥ 400 → confidence=0.8
        # Q-1 YoY = (0.44-0.40)*10000 = 400bp ≥ 200 ✓
        _insert_6_seasons_for_t2(
            db_session,
            gross_series=[0.46, 0.44, 0.43, 0.42, 0.42, 0.40],
        )
        svc = RepricingTriggerService(db_session)
        result = svc._detect_margin_expansion("AAPL", date(2026, 4, 1))

        assert result is not None
        assert result.confidence == pytest.approx(0.8)
        assert result.evidence["trigger_metric"] == "gross_margin"
        assert result.evidence["expansion_bp"] == 400

    def test_m6_fcf_arm_only_hit(self, db_session: Session) -> None:
        """FCF arm only: gross flat, fcf both YoY ≥ 300bp → trigger_metric=fcf_margin."""
        # gross all 0.40 → Q0 YoY=0 < 200 → no gross hit
        # fcf [0.30, 0.28, 0.26, 0.25, 0.24, 0.23]:
        #   Q0 YoY = (0.30-0.24)*10000 = 600bp ≥ 300 ✓
        #   Q-1 YoY = (0.28-0.23)*10000 = 500bp ≥ 300 ✓
        _insert_6_seasons_for_t2(
            db_session,
            gross_series=[0.40, 0.40, 0.40, 0.40, 0.40, 0.40],
            fcf_series=[0.30, 0.28, 0.26, 0.25, 0.24, 0.23],
        )
        svc = RepricingTriggerService(db_session)
        result = svc._detect_margin_expansion("AAPL", date(2026, 4, 1))

        assert result is not None
        assert result.evidence["trigger_metric"] == "fcf_margin"
        assert result.evidence["expansion_bp"] == 600  # fcf Q0 YoY = 600bp
        # fcf_trend [Q-2, Q-1, Q0]: rows[2].fcf=0.26, rows[1].fcf=0.28, rows[0].fcf=0.30
        assert result.evidence["fcf_margin_trend"] == pytest.approx([0.26, 0.28, 0.30])

    def test_m7_both_arms_hit_gross_preferred(self, db_session: Session) -> None:
        """Both gross + fcf arms hit → trigger_metric=gross_margin (D096 默认偏好)."""
        _insert_6_seasons_for_t2(
            db_session,
            gross_series=[0.46, 0.44, 0.43, 0.42, 0.42, 0.40],  # Q0 YoY=400bp
            fcf_series=[0.30, 0.28, 0.26, 0.25, 0.24, 0.23],    # Q0 YoY=600bp
        )
        svc = RepricingTriggerService(db_session)
        result = svc._detect_margin_expansion("AAPL", date(2026, 4, 1))

        assert result is not None
        assert result.evidence["trigger_metric"] == "gross_margin"
        assert result.evidence["expansion_bp"] == 400  # gross Q0 YoY (not fcf's 600)

    def test_m8_only_one_season_yoy_passes_no_trigger(self, db_session: Session) -> None:
        """Q0 YoY ≥ threshold but Q-1 YoY < threshold → gross arm not hit → return None."""
        # Q0 YoY = (0.46-0.42)*10000 = 400bp ≥ 200 ✓
        # Q-1 YoY = (0.41-0.40)*10000 = 100bp < 200 ✗
        # → gross_hit = False; fcf all None → fcf_hit = False → return None
        _insert_6_seasons_for_t2(
            db_session,
            gross_series=[0.46, 0.41, 0.41, 0.41, 0.42, 0.40],
        )
        svc = RepricingTriggerService(db_session)
        result = svc._detect_margin_expansion("AAPL", date(2026, 4, 1))
        assert result is None

    @pytest.mark.parametrize(
        "n_rows, gross_series, fcf_series, label",
        [
            # (a) fewer than 6 rows → insufficient history
            (5, [0.46, 0.44, 0.43, 0.42, 0.42], [None] * 5, "insufficient_rows"),
            # (b) 6 rows, both margins all None → both arms skip → return None
            (6, [None] * 6, [None] * 6, "all_null_margins"),
            # (c) 6 rows, gross flat (0bp expansion) + fcf None → no arm hits
            (6, [0.40] * 6, [None] * 6, "no_expansion"),
        ],
    )
    def test_m9_return_none_scenarios(
        self,
        db_session: Session,
        n_rows: int,
        gross_series: list[float | None],
        fcf_series: list[float | None],
        label: str,
    ) -> None:
        """Various data conditions that produce return None."""
        if n_rows < 6:
            for i in range(n_rows):
                _km(
                    db_session,
                    fiscal_quarter=_FQ[i],
                    period_end_date=_DATES[i],
                    gross_margin=gross_series[i] if gross_series else None,
                    fcf_margin=fcf_series[i] if fcf_series else None,
                )
        else:
            _insert_6_seasons_for_t2(
                db_session,
                gross_series=gross_series,
                fcf_series=fcf_series,
            )

        svc = RepricingTriggerService(db_session)
        result = svc._detect_margin_expansion("AAPL", date(2026, 4, 1))
        assert result is None, f"Expected None for scenario: {label}"


# ── Class 3: End-to-end ───────────────────────────────────────────────────────


class TestMarginExpansionEndToEnd:

    def test_m10_hit_upserts_then_miss_soft_expires(self, db_session: Session) -> None:
        """Full pipeline: T2 hit → upsert repricing_triggers; re-scan miss → soft expire."""
        _stock(db_session, "AAPL")
        # Low-confidence gross arm hit: Q0 YoY=200bp, Q-1 YoY=300bp → confidence=0.5
        _insert_6_seasons_for_t2(db_session, ticker="AAPL")

        svc = RepricingTriggerService(db_session)
        scan_date = date(2026, 4, 1)
        counts = svc.compute_and_store_all_triggers(scan_date=scan_date)

        assert counts["MARGIN_EXPANSION"] == 1

        row = db_session.execute(
            select(RepricingTrigger).where(
                RepricingTrigger.ticker == "AAPL",
                RepricingTrigger.trigger_type == "MARGIN_EXPANSION",
            )
        ).scalar_one()

        assert row.active is True
        assert row.confidence == pytest.approx(0.5)

        ev = json.loads(row.evidence_json)
        assert set(ev.keys()) == {
            "gross_margin_trend", "fcf_margin_trend", "quarters",
            "trigger_metric", "expansion_bp",
        }
        assert ev["trigger_metric"] == "gross_margin"
        assert isinstance(ev["expansion_bp"], int)
        assert len(ev["gross_margin_trend"]) == 3
        assert len(ev["fcf_margin_trend"]) == 3
        assert len(ev["quarters"]) == 3

        # Re-scan with flat gross → T2 misses → soft expire
        db_session.query(StockKeyMetricsQuarterly).delete()
        db_session.commit()
        _insert_6_seasons_for_t2(
            db_session,
            ticker="AAPL",
            gross_series=[0.40] * 6,  # 0bp expansion → no hit
        )

        counts2 = svc.compute_and_store_all_triggers(scan_date=date(2026, 4, 2))
        assert counts2["MARGIN_EXPANSION"] == 0

        db_session.expire_all()
        row_after = db_session.execute(
            select(RepricingTrigger).where(
                RepricingTrigger.ticker == "AAPL",
                RepricingTrigger.trigger_type == "MARGIN_EXPANSION",
            )
        ).scalar_one()
        assert row_after.active is False
