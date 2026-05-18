"""F217-c1: capitulationEvidence backend wiring tests.

T1-T4: pure unit tests (schema + helper).
T5-T8: integration tests seeding real db_session.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.models.daily_bar import DailyBar
from app.models.market_regime_snapshot import MarketRegimeSnapshot
from app.models.setup_snapshot import SetupSnapshot
from app.models.stock import Stock
from app.models.user_settings import UserSettings
from app.schemas.cockpit.decision import CapitulationEvidence, DecisionData
from app.services.cockpit.cockpit_params import REGIME
from app.services.cockpit.decision_service import compute_decision
from app.services.cockpit.setup_service import compute_capitulation_evidence


# ─── T1: CapitulationEvidence model — alias serialization ────────────────────


class TestT1Schema:
    def test_camel_aliases(self):
        ev = CapitulationEvidence(vol_zscore=2.71, drop_5d_pct=-12.4, reversal_day=True)
        dumped = ev.model_dump(by_alias=True)
        assert dumped == {"volZscore": 2.71, "drop5dPct": -12.4, "reversalDay": True}

    def test_construct_via_alias(self):
        ev = CapitulationEvidence.model_validate(
            {"volZscore": 3.1, "drop5dPct": -8.0, "reversalDay": False}
        )
        assert ev.vol_zscore == 3.1
        assert ev.drop_5d_pct == -8.0
        assert ev.reversal_day is False

    def test_decision_data_nested_alias(self):
        ev = CapitulationEvidence(vol_zscore=2.71, drop_5d_pct=-12.4, reversal_day=True)
        dd = DecisionData(
            ticker="TEST",
            setup_type="CAPITULATION",
            setup_quality="A",
            entry_price=150.0,
            stop_price=140.0,
            target_2r=170.0,
            target_3r=180.0,
            reward_risk=2.0,
            risk_per_share=10.0,
            suggested_shares=5,
            position_value=750.0,
            account_risk_pct=0.5,
            effective_risk_pct=0.5,
            regime_cap=1.0,
            user_setting_cap=0.5,
            earnings_risk="SAFE",
            earnings_date=None,
            deterministic_hash="abc123",
            capitulation_evidence=ev,
        )
        full = dd.model_dump(by_alias=True)
        assert full["capitulationEvidence"] == {
            "volZscore": 2.71,
            "drop5dPct": -12.4,
            "reversalDay": True,
        }

    def test_capitulation_evidence_default_none(self):
        dd = DecisionData(
            ticker="MSFT",
            setup_type="BREAKOUT",
            setup_quality="B",
            entry_price=300.0,
            stop_price=290.0,
            target_2r=320.0,
            target_3r=330.0,
            reward_risk=2.0,
            risk_per_share=10.0,
            suggested_shares=3,
            position_value=900.0,
            account_risk_pct=0.3,
            effective_risk_pct=0.3,
            regime_cap=1.0,
            user_setting_cap=0.5,
            earnings_risk=None,
            earnings_date=None,
            deterministic_hash="xyz",
        )
        assert dd.capitulation_evidence is None
        full = dd.model_dump(by_alias=True)
        assert full["capitulationEvidence"] is None


# ─── T2: compute_capitulation_evidence happy path ────────────────────────────


class TestT2HelperHappyPath:
    def test_drop_and_reversal_day_true(self):
        # close=105, H=110, L=90 → (105-90)/20=0.75 >= (1-0.333) → reversal_day=True
        # drop = (105-120)/120*100 = -12.5
        closes = [120.0, 115.0, 112.0, 108.0, 104.0, 105.0]
        highs  = [122.0, 117.0, 114.0, 110.0, 106.0, 110.0]
        lows   = [118.0, 113.0, 110.0, 106.0, 102.0,  90.0]
        result = compute_capitulation_evidence(closes, highs, lows)
        assert result is not None
        assert result["drop_5d_pct"] == round((105.0 - 120.0) / 120.0 * 100, 1)
        assert result["reversal_day"] is True

    def test_drop_positive(self):
        # When stock recovered: closes[-1] > closes[-6]
        closes = [80.0, 85.0, 88.0, 90.0, 93.0, 88.0]
        highs  = [86.0, 87.0, 90.0, 92.0, 95.0, 95.0]
        lows   = [79.0, 83.0, 86.0, 88.0, 91.0, 80.0]
        result = compute_capitulation_evidence(closes, highs, lows)
        assert result is not None
        assert result["drop_5d_pct"] == round((88.0 - 80.0) / 80.0 * 100, 1)

    def test_extra_bars_uses_last_6(self):
        # Only the last 6 bars matter; extra leading bars should not affect result
        closes = [200.0, 190.0, 180.0, 120.0, 115.0, 112.0, 108.0, 104.0, 105.0]
        highs  = [210.0, 195.0, 185.0, 122.0, 117.0, 114.0, 110.0, 106.0, 110.0]
        lows   = [195.0, 185.0, 175.0, 118.0, 113.0, 110.0, 106.0, 102.0,  90.0]
        result = compute_capitulation_evidence(closes, highs, lows)
        # closes[-6]=120, closes[-1]=105 → -12.5
        assert result is not None
        assert result["drop_5d_pct"] == round((105.0 - 120.0) / 120.0 * 100, 1)


# ─── T3: compute_capitulation_evidence None branches ─────────────────────────


class TestT3HelperNoneBranches:
    def test_fewer_than_6_bars(self):
        assert compute_capitulation_evidence([100.0]*3, [105.0]*3, [95.0]*3) is None

    def test_exactly_5_bars(self):
        assert compute_capitulation_evidence([100.0]*5, [105.0]*5, [95.0]*5) is None

    def test_empty_list(self):
        assert compute_capitulation_evidence([], [], []) is None

    def test_base_zero(self):
        # closes[-6] == 0 → division by zero guard
        closes = [0.0, 101.0, 102.0, 103.0, 104.0, 105.0]
        assert compute_capitulation_evidence(closes, [106.0]*6, [99.0]*6) is None

    def test_exactly_6_bars_valid(self):
        closes = [120.0, 115.0, 112.0, 108.0, 104.0, 105.0]
        highs  = [122.0, 117.0, 114.0, 110.0, 106.0, 110.0]
        lows   = [118.0, 113.0, 110.0, 106.0, 102.0,  90.0]
        assert compute_capitulation_evidence(closes, highs, lows) is not None


# ─── T4: compute_capitulation_evidence reversal_day=False branch ─────────────


class TestT4HelperReversalDayFalse:
    def test_close_in_lower_bin(self):
        # close=92, H=110, L=90 → (92-90)/20=0.1 < 0.667 → reversal_day=False
        # drop_5d_pct is still computed normally
        closes = [120.0, 115.0, 112.0, 108.0, 104.0, 92.0]
        highs  = [122.0, 117.0, 114.0, 110.0, 106.0, 110.0]
        lows   = [118.0, 113.0, 110.0, 106.0, 102.0,  90.0]
        result = compute_capitulation_evidence(closes, highs, lows)
        assert result is not None
        assert result["reversal_day"] is False
        assert result["drop_5d_pct"] == round((92.0 - 120.0) / 120.0 * 100, 1)

    def test_close_at_low_flat_range(self):
        # H == L → day_range = 0 → _check_close_in_upper_bin returns False
        closes = [120.0, 115.0, 112.0, 108.0, 104.0, 100.0]
        highs  = [122.0, 117.0, 114.0, 110.0, 106.0, 100.0]
        lows   = [118.0, 113.0, 110.0, 106.0, 102.0, 100.0]
        result = compute_capitulation_evidence(closes, highs, lows)
        assert result is not None
        assert result["reversal_day"] is False


# ─── Integration test seed helpers ───────────────────────────────────────────

_SCAN_DATE = date(2026, 5, 18)


def _seed_stock(db, ticker: str = "CAPT") -> Stock:
    s = Stock(ticker=ticker, name=f"{ticker} Inc", exchange="NYSE", is_active=True,
               added_at=datetime.now(timezone.utc))
    db.add(s)
    db.flush()
    return s


def _seed_6_bars(db, stock_id: int, ticker: str = "CAPT") -> None:
    """Seed 6 ascending-date DailyBar rows that produce drop_5d_pct≈-12.5 and reversal_day=True.

    Bar dates: 2026-05-11 … 2026-05-18 (only 6 bars seeded for simplicity).
    closes[-6]=120, closes[-1]=105; H[-1]=110, L[-1]=90 → reversal_day True.
    """
    bars_data = [
        # (date, open, high, low, close, volume)
        (date(2026, 5, 11), 119.0, 122.0, 118.0, 120.0, 1_000_000),
        (date(2026, 5, 12), 114.0, 117.0, 113.0, 115.0, 1_200_000),
        (date(2026, 5, 13), 111.0, 114.0, 110.0, 112.0, 1_100_000),
        (date(2026, 5, 14), 107.0, 110.0, 106.0, 108.0, 1_300_000),
        (date(2026, 5, 15), 103.0, 106.0, 102.0, 104.0, 1_400_000),
        # Last bar: close=105, H=110, L=90 → (105-90)/20=0.75 → reversal_day=True
        (date(2026, 5, 18), 92.0,  110.0,  90.0, 105.0, 3_500_000),
    ]
    for (d, o, h, lo, c, v) in bars_data:
        db.add(DailyBar(stock_id=stock_id, date=d, open=o, high=h, low=lo, close=c, volume=v))
    db.flush()


def _seed_snapshot(
    db,
    ticker: str = "CAPT",
    setup_type: str = "CAPITULATION",
    volume_zscore: float | None = 2.71,
    entry_price: float = 106.0,
    stop_price: float = 88.0,
) -> SetupSnapshot:
    snap = SetupSnapshot(
        ticker=ticker,
        scan_date=_SCAN_DATE,
        setup_type=setup_type,
        setup_quality="A",
        entry_price=entry_price,
        stop_price=stop_price,
        target_2r=entry_price + 2 * (entry_price - stop_price),
        target_3r=entry_price + 3 * (entry_price - stop_price),
        reward_risk=2.0,
        distance_to_entry_pct=0.9,
        rs_percentile=80.0,
        volume_status="HIGH",
        trend_score=4,
        earnings_risk="SAFE",
        ready_signal=True,
        suggested_action="enter",
        volume_zscore=volume_zscore,
        scanned_at=datetime.now(timezone.utc),
    )
    db.add(snap)
    db.flush()
    return snap


def _seed_regime(db) -> MarketRegimeSnapshot:
    cap = REGIME.SINGLE_TRADE_RISK_PCT["CONSTRUCTIVE"]
    row = MarketRegimeSnapshot(
        date=_SCAN_DATE,
        regime="CONSTRUCTIVE",
        market_score=65,
        spy_trend_score=20,
        qqq_trend_score=15,
        iwm_breadth_score=10,
        sector_participation_score=8,
        risk_appetite_score=8,
        volatility_stress_score=8,
        allowed_exposure_pct=70.0,
        single_trade_risk_pct=cap,
        preferred_setups='["BREAKOUT","CAPITULATION"]',
        avoid_setups='["EXTENDED"]',
    )
    db.add(row)
    db.flush()
    return row


def _seed_user_settings(db) -> UserSettings:
    row = UserSettings(
        id=1,
        account_size=100_000.0,
        max_exposure_pct=80.0,
        single_trade_risk_pct=1.0,
        default_risk_per_trade_pct=0.75,
        base_currency="USD",
        updated_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.flush()
    return row


def _seed_full(db, ticker: str = "CAPT", setup_type: str = "CAPITULATION",
               volume_zscore: float | None = 2.71, n_bars: int = 6) -> None:
    stock = _seed_stock(db, ticker)
    if n_bars >= 6:
        _seed_6_bars(db, stock.id, ticker)
    elif n_bars > 0:
        # Seed fewer than 6 bars for T8
        bars_data = [
            (date(2026, 5, 16), 103.0, 106.0, 102.0, 104.0, 1_400_000),
            (date(2026, 5, 17), 102.0, 105.0, 101.0, 103.0, 1_300_000),
            (date(2026, 5, 18),  92.0, 110.0,  90.0, 105.0, 3_500_000),
        ][:n_bars]
        for d, o, h, lo, c, v in bars_data:
            db.add(DailyBar(stock_id=stock.id, date=d, open=o, high=h, low=lo, close=c, volume=v))
        db.flush()
    _seed_snapshot(db, ticker, setup_type=setup_type, volume_zscore=volume_zscore)
    _seed_regime(db)
    _seed_user_settings(db)
    db.commit()


# ─── T5: CAPITULATION + bars充足 → capitulationEvidence filled ───────────────


class TestT5CapitulationWithEvidence:
    def test_evidence_fields_populated(self, db_session):
        _seed_full(db_session, setup_type="CAPITULATION", volume_zscore=2.71)
        result = compute_decision(db_session, "CAPT")
        assert result.capitulation_evidence is not None
        ev = result.capitulation_evidence
        assert ev.vol_zscore == 2.71
        # closes[-6]=120, closes[-1]=105 → -12.5
        assert ev.drop_5d_pct == round((105.0 - 120.0) / 120.0 * 100, 1)
        assert ev.reversal_day is True

    def test_response_model_dump_camel_case(self, db_session):
        _seed_full(db_session, setup_type="CAPITULATION", volume_zscore=2.71)
        result = compute_decision(db_session, "CAPT")
        dumped = result.model_dump(by_alias=True)
        cap_ev = dumped.get("capitulationEvidence")
        assert cap_ev is not None
        assert cap_ev["volZscore"] == 2.71
        assert cap_ev["drop5dPct"] == round((105.0 - 120.0) / 120.0 * 100, 1)
        assert cap_ev["reversalDay"] is True


# ─── T6: non-CAPITULATION setup → capitulationEvidence is None ───────────────


class TestT6NonCapitulation:
    def test_breakout_no_evidence(self, db_session):
        _seed_full(db_session, setup_type="BREAKOUT", volume_zscore=2.5)
        result = compute_decision(db_session, "CAPT")
        assert result.capitulation_evidence is None

    def test_reclaim_no_evidence(self, db_session):
        # Use a different ticker to avoid PK collision
        stock = _seed_stock(db_session, "RCLM")
        _seed_6_bars(db_session, stock.id, "RCLM")
        _seed_snapshot(db_session, "RCLM", setup_type="RECLAIM", volume_zscore=1.0)
        _seed_regime(db_session)
        _seed_user_settings(db_session)
        db_session.commit()
        result = compute_decision(db_session, "RCLM")
        assert result.capitulation_evidence is None


# ─── T7: CAPITULATION + volume_zscore=None → capitulationEvidence is None ────


class TestT7VolumeZscoreNone:
    def test_null_zscore_returns_none_evidence(self, db_session):
        _seed_full(db_session, setup_type="CAPITULATION", volume_zscore=None)
        result = compute_decision(db_session, "CAPT")
        assert result.capitulation_evidence is None


# ─── T8: CAPITULATION + bars < 6 → capitulationEvidence is None ──────────────


class TestT8InsufficientBars:
    def test_3_bars_returns_none_evidence(self, db_session):
        _seed_full(db_session, setup_type="CAPITULATION", volume_zscore=2.71, n_bars=3)
        result = compute_decision(db_session, "CAPT")
        assert result.capitulation_evidence is None
