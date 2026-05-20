"""F218-d5 tests — T4 SECTOR_CYCLE detector (sector mapping + RS percentile + SMA200).

10 tests grouped into 3 classes:
  TestSectorMapping        — S1–S2  (ticker → ETF mapping, happy + fail paths)
  TestSectorCycleDetector  — S3–S9  (core detector: happy / crossing failure / price gate / data)
  TestSectorCycleEndToEnd  — S10    (compute_and_store_all_triggers: write + upsert + soft expire)
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Stock
from app.models.market_index import MarketIndex
from app.models.market_scan_universe import MarketScanUniverse
from app.models.repricing_trigger import RepricingTrigger
from app.services.cockpit.cockpit_params import SHARED
from app.services.cockpit.repricing_trigger_service import RepricingTriggerService

# ── Test constants ─────────────────────────────────────────────────────────────

_SCAN_DATE  = date(2026, 5, 20)
_START_DATE = _SCAN_DATE - timedelta(days=60)   # 2026-03-21 (start sample point)
_D120       = _SCAN_DATE - timedelta(days=120)  # 2026-01-20 (RS lookback for start_date)

# SPY: linear growth 100 → 102 → 104
# spy_return_start  = 102/100 - 1 = 0.02
# spy_return_end    = 104/102 - 1 ≈ 0.01961
_SPY_D120, _SPY_D60, _SPY_D = 100.0, 102.0, 104.0

# XLK (Technology, target):
#   ratio_start = (100.2/100 - 1) / 0.02  = 0.1  → rank 1 / 11 → pct ≈  4.55 < 40
#   ratio_end   = (119.83/100.2 - 1) / (104/102 - 1) ≈ 10.0 → rank 11/11 → pct ≈ 95.45 > 60
_XLK_D120, _XLK_D60, _XLK_D = 100.0, 100.2, 119.83

# Other 10 ETFs: ratio = 2.0 at both sample points (neutral, mid-pack)
#   ratio_start = (104/100 - 1) / 0.02 = 2.0
#   ratio_end   = (108.08/104 - 1) / (104/102 - 1) ≈ 2.0
_OTHER_D120, _OTHER_D60, _OTHER_D = 100.0, 104.0, 108.08

_OTHER_ETFS: list[str] = [e for e in SHARED.SECTOR_ETFS if e != "XLK"]

# ── Test helpers ──────────────────────────────────────────────────────────────


def _stock(db: Session, ticker: str = "NVDA") -> Stock:
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


def _seed_market_index(
    db: Session, symbol: str, dates_closes: list[tuple[date, float]],
) -> None:
    for d, c in dates_closes:
        db.add(MarketIndex(symbol=symbol, name=f"{symbol} index", date=d, close=c))
    db.commit()


def _seed_universe(db: Session, ticker: str, sector: str | None) -> None:
    db.add(MarketScanUniverse(
        ticker=ticker,
        company_name=f"{ticker} Corp",
        exchange="NASDAQ",
        market_cap=1_000_000_000,
        sector=sector,
        last_seen_at=datetime.now(timezone.utc),
    ))
    db.commit()


def _spy_closes() -> list[tuple[date, float]]:
    """3 key dates for SPY (enough for RS computation at both sample points)."""
    return [(_D120, _SPY_D120), (_START_DATE, _SPY_D60), (_SCAN_DATE, _SPY_D)]


def _other_etf_closes() -> list[tuple[date, float]]:
    """3 key dates for each of the 10 non-target ETFs (RS computation only)."""
    return [(_D120, _OTHER_D120), (_START_DATE, _OTHER_D60), (_SCAN_DATE, _OTHER_D)]


def _xlk_closes_happy(extra_low_price: float = 90.0) -> list[tuple[date, float]]:
    """200-calendar-day series for XLK: 197 filler rows at extra_low_price + 3 key dates.

    Produces start_pct ≈ 4.55 < 40, end_pct ≈ 95.45 > 60.
    SMA200 with extra_low_price=90 → SMA ≈ 90.25 < latest_close=119.83 → price gate passes.
    SMA200 with extra_low_price=200 → SMA ≈ 198.6 > latest_close=119.83 → price gate fails.
    """
    result: list[tuple[date, float]] = []
    for i in range(199, -1, -1):
        d = _SCAN_DATE - timedelta(days=i)
        if d == _D120:
            c = _XLK_D120
        elif d == _START_DATE:
            c = _XLK_D60
        elif d == _SCAN_DATE:
            c = _XLK_D
        else:
            c = extra_low_price
        result.append((d, c))
    return result


def _seed_full_happy_path(db: Session) -> None:
    """Seed SPY + 11 ETF closes for a happy-path SECTOR_CYCLE trigger on XLK."""
    _seed_market_index(db, "SPY", _spy_closes())
    _seed_market_index(db, "XLK", _xlk_closes_happy())
    for etf in _OTHER_ETFS:
        _seed_market_index(db, etf, _other_etf_closes())


# ── TestSectorMapping (S1–S2) ─────────────────────────────────────────────────


class TestSectorMapping:
    """S1–S2: ticker → sector → SECTOR_TO_ETF mapping (happy + fail paths)."""

    def test_s1_happy_technology_maps_to_xlk_and_triggers(
        self, db_session: Session,
    ) -> None:
        """S1: ticker with sector="Technology" → mapped to XLK; full trigger fires."""
        _stock(db_session, "NVDA")
        _seed_universe(db_session, "NVDA", "Technology")
        _seed_full_happy_path(db_session)

        result = RepricingTriggerService(db_session)._detect_sector_cycle("NVDA", _SCAN_DATE)

        assert result is not None
        assert result.evidence["sector"] == "XLK"

    def test_s2_mapping_fail_paths_return_none(self, db_session: Session) -> None:
        """S2: not in universe / NULL sector / unknown sector → None without exception."""
        _stock(db_session, "AAPL")
        _stock(db_session, "GOOG")
        _seed_full_happy_path(db_session)
        svc = RepricingTriggerService(db_session)

        # not in universe at all
        assert svc._detect_sector_cycle("AAPL", _SCAN_DATE) is None

        # in universe but sector = NULL
        _seed_universe(db_session, "AAPL", None)
        assert svc._detect_sector_cycle("AAPL", _SCAN_DATE) is None

        # sector string not in SECTOR_TO_ETF
        _seed_universe(db_session, "GOOG", "Unknown Sector")
        assert svc._detect_sector_cycle("GOOG", _SCAN_DATE) is None


# ── TestSectorCycleDetector (S3–S9) ──────────────────────────────────────────


class TestSectorCycleDetector:
    """S3–S9: core detector logic — happy / crossing failure / price gate / data edge cases."""

    def test_s3_happy_full_trigger_evidence_schema(self, db_session: Session) -> None:
        """S3: start_pct<40 AND end_pct>60 AND close>SMA200 → trigger; evidence schema correct."""
        _stock(db_session)
        _seed_universe(db_session, "NVDA", "Technology")
        _seed_full_happy_path(db_session)

        result = RepricingTriggerService(db_session)._detect_sector_cycle("NVDA", _SCAN_DATE)

        assert result is not None
        assert result.confidence == 0.5

        ev = result.evidence
        assert ev["sector"] == "XLK"

        rs = ev["rs_history"]
        assert isinstance(rs, list) and len(rs) == 2
        assert rs[0]["date"] == _START_DATE.isoformat()   # ASC: oldest first
        assert rs[1]["date"] == _SCAN_DATE.isoformat()
        assert rs[0]["percentile"] < 40.0
        assert rs[1]["percentile"] > 60.0

        assert isinstance(ev["price_vs_200d"], float)
        assert ev["price_vs_200d"] > 1.0  # latest_close > SMA200

    def test_s4_start_pct_not_below_40_returns_none(self, db_session: Session) -> None:
        """S4: start_pct ≥ 40 (XLK ratio=2.5 at start, highest among 11) → return None."""
        _stock(db_session)
        _seed_universe(db_session, "NVDA", "Technology")
        _seed_market_index(db_session, "SPY", _spy_closes())
        for etf in _OTHER_ETFS:
            _seed_market_index(db_session, etf, _other_etf_closes())

        # XLK at D-60: 105.0 → ratio_start = (105/100-1)/0.02 = 2.5 (highest → pct≈95.45 ≥ 40)
        # XLK at D:   125.59 → ratio_end ≈ 10.0 (end gate would pass, but start gate fires first)
        xlk_dict = dict(_xlk_closes_happy())
        xlk_dict[_START_DATE] = 105.0
        xlk_dict[_SCAN_DATE] = 125.59
        _seed_market_index(db_session, "XLK", sorted(xlk_dict.items()))

        result = RepricingTriggerService(db_session)._detect_sector_cycle("NVDA", _SCAN_DATE)
        assert result is None

    def test_s5_end_pct_not_above_60_returns_none(self, db_session: Session) -> None:
        """S5: end_pct ≤ 60 (XLK ratio≈1.5 at end, lowest among 11) → return None."""
        _stock(db_session)
        _seed_universe(db_session, "NVDA", "Technology")
        _seed_market_index(db_session, "SPY", _spy_closes())
        for etf in _OTHER_ETFS:
            _seed_market_index(db_session, etf, _other_etf_closes())

        # XLK at D-60: 100.2 (ratio_start=0.1 → start_pct≈4.55 < 40, passes)
        # XLK at D:   103.15 → ratio_end = (103.15/100.2-1)/(104/102-1) ≈ 1.5 (lowest → pct≈4.55 ≤ 60)
        xlk_dict = dict(_xlk_closes_happy())
        xlk_dict[_SCAN_DATE] = 103.15
        _seed_market_index(db_session, "XLK", sorted(xlk_dict.items()))

        result = RepricingTriggerService(db_session)._detect_sector_cycle("NVDA", _SCAN_DATE)
        assert result is None

    def test_s6_close_below_sma200_no_trigger(self, db_session: Session) -> None:
        """S6: RS gates pass but latest_close ≤ SMA200 → return None."""
        _stock(db_session)
        _seed_universe(db_session, "NVDA", "Technology")
        _seed_market_index(db_session, "SPY", _spy_closes())
        for etf in _OTHER_ETFS:
            _seed_market_index(db_session, etf, _other_etf_closes())

        # Filler price = 200.0 → SMA200 ≈ 198.6 > latest_close=119.83 → price gate fails
        _seed_market_index(db_session, "XLK", _xlk_closes_happy(extra_low_price=200.0))

        result = RepricingTriggerService(db_session)._detect_sector_cycle("NVDA", _SCAN_DATE)
        assert result is None

    def test_s7_insufficient_spy_data_no_error_returns_none(
        self, db_session: Session,
    ) -> None:
        """S7: SPY has only 50 recent rows (no close at D-120 lookback) → population None → None."""
        _stock(db_session)
        _seed_universe(db_session, "NVDA", "Technology")
        # SPY: only 50 days [scan_date-49 … scan_date], no data at D-120
        spy_50 = [(_SCAN_DATE - timedelta(days=i), 100.0 + i * 0.1) for i in range(49, -1, -1)]
        _seed_market_index(db_session, "SPY", spy_50)
        _seed_market_index(db_session, "XLK", _xlk_closes_happy())
        for etf in _OTHER_ETFS:
            _seed_market_index(db_session, etf, _other_etf_closes())

        result = RepricingTriggerService(db_session)._detect_sector_cycle("NVDA", _SCAN_DATE)
        assert result is None  # no ZeroDivisionError / IndexError

    def test_s8_etf_missing_lookback_close_returns_none(self, db_session: Session) -> None:
        """S8: XLE has no close at D-120 → _rs_ratio_population returns None → None."""
        _stock(db_session)
        _seed_universe(db_session, "NVDA", "Technology")
        _seed_market_index(db_session, "SPY", _spy_closes())
        _seed_market_index(db_session, "XLK", _xlk_closes_happy())
        for etf in _OTHER_ETFS:
            if etf == "XLE":
                # XLE only has D-60 and D — missing D-120 lookback row
                _seed_market_index(db_session, etf, [(_START_DATE, 104.0), (_SCAN_DATE, 108.0)])
            else:
                _seed_market_index(db_session, etf, _other_etf_closes())

        result = RepricingTriggerService(db_session)._detect_sector_cycle("NVDA", _SCAN_DATE)
        assert result is None

    def test_s9_spy_return_near_zero_returns_none(self, db_session: Session) -> None:
        """S9: SPY return ≈ 0 at end_date → ratio unstable → _rs_ratio_population None → None."""
        _stock(db_session)
        _seed_universe(db_session, "NVDA", "Technology")
        # SPY: D-120=100, D-60=102 (start computation passes), D=102.0001 (end return≈0 fails)
        spy_flat_end = [(_D120, 100.0), (_START_DATE, 102.0), (_SCAN_DATE, 102.0001)]
        _seed_market_index(db_session, "SPY", spy_flat_end)
        _seed_market_index(db_session, "XLK", _xlk_closes_happy())
        for etf in _OTHER_ETFS:
            _seed_market_index(db_session, etf, _other_etf_closes())

        result = RepricingTriggerService(db_session)._detect_sector_cycle("NVDA", _SCAN_DATE)
        assert result is None


# ── TestSectorCycleEndToEnd (S10) ─────────────────────────────────────────────


class TestSectorCycleEndToEnd:
    """S10: compute_and_store_all_triggers — write trigger + idempotent upsert + soft expire."""

    def test_s10_e2e_write_upsert_soft_expire(self, db_session: Session) -> None:
        """S10: full E2E across 3 runs — write / upsert-idempotent / soft-expire."""
        _stock(db_session, "NVDA")
        _seed_universe(db_session, "NVDA", "Technology")
        _seed_full_happy_path(db_session)

        svc = RepricingTriggerService(db_session)

        # Run 1: should write 1 SECTOR_CYCLE row, active=True
        svc.compute_and_store_all_triggers(_SCAN_DATE)
        rows = db_session.execute(
            select(RepricingTrigger)
            .where(RepricingTrigger.ticker == "NVDA")
            .where(RepricingTrigger.trigger_type == "SECTOR_CYCLE")
        ).scalars().all()
        assert len(rows) == 1
        t = rows[0]
        assert t.active is True
        assert t.confidence == 0.5
        ev = json.loads(t.evidence_json)
        assert "sector" in ev
        assert "rs_history" in ev
        assert "price_vs_200d" in ev

        # Run 2 (same data): idempotent upsert — still 1 row, still active=True
        svc.compute_and_store_all_triggers(_SCAN_DATE)
        after_upsert = db_session.execute(
            select(RepricingTrigger)
            .where(RepricingTrigger.ticker == "NVDA")
            .where(RepricingTrigger.trigger_type == "SECTOR_CYCLE")
        ).scalars().all()
        assert len(after_upsert) == 1
        assert after_upsert[0].active is True

        # Run 3 (next day): remove XLK closes → detector returns None → soft expire active → False
        # soft_expire filters detected_date < current_date, so we must advance scan_date by 1
        db_session.execute(delete(MarketIndex).where(MarketIndex.symbol == "XLK"))
        db_session.commit()
        next_day = _SCAN_DATE + timedelta(days=1)
        svc.compute_and_store_all_triggers(next_day)
        after_expire = db_session.execute(
            select(RepricingTrigger)
            .where(RepricingTrigger.ticker == "NVDA")
            .where(RepricingTrigger.trigger_type == "SECTOR_CYCLE")
        ).scalars().all()
        assert len(after_expire) == 1
        assert after_expire[0].active is False
