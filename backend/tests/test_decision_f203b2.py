"""F203-b2 Decision 服务 + 接入层测试 — Sprint Contract S1–S12.

Service unit tests (S1–S7): call compute_decision() directly via db_session.
Router integration tests (S8–S12): use TestClient (client fixture) + db_session seeding.
"""

from __future__ import annotations

import hashlib
import math
from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.earnings_event import EarningsEvent
from app.models.market_regime_snapshot import MarketRegimeSnapshot
from app.models.setup_snapshot import SetupSnapshot
from app.models.user_settings import UserSettings
from app.schemas.cockpit.decision import DecisionData
from app.services.cockpit.cockpit_params import DECISION, REGIME, SETUP
from app.services.cockpit.decision_service import compute_decision

# ─── Seed helpers ─────────────────────────────────────────────────────────────


def _seed_snapshot(
    db,
    ticker: str = "NVDA",
    scan_date: date | None = None,
    entry_price: float = 850.0,
    stop_price: float = 820.0,
    setup_type: str = "BREAKOUT",
    setup_quality: str = "A",
    reward_risk: float = 2.0,
    **kwargs,
) -> SetupSnapshot:
    snap = SetupSnapshot(
        ticker=ticker,
        scan_date=scan_date or date(2026, 4, 25),
        setup_type=setup_type,
        setup_quality=setup_quality,
        entry_price=entry_price,
        stop_price=stop_price,
        target_2r=entry_price + 2 * (entry_price - stop_price),
        target_3r=entry_price + 3 * (entry_price - stop_price),
        reward_risk=reward_risk,
        distance_to_entry_pct=1.0,
        rs_percentile=85.0,
        volume_status="HIGH",
        trend_score=4,
        earnings_risk="SAFE",
        ready_signal=True,
        suggested_action="enter",
        scanned_at=datetime.now(timezone.utc),
        **kwargs,
    )
    db.add(snap)
    db.flush()
    return snap


def _seed_regime(
    db,
    regime: str = "CONSTRUCTIVE",
    single_trade_risk_pct: float | None = None,
    snapshot_date: date | None = None,
) -> MarketRegimeSnapshot:
    cap = single_trade_risk_pct if single_trade_risk_pct is not None else REGIME.SINGLE_TRADE_RISK_PCT[regime]
    row = MarketRegimeSnapshot(
        date=snapshot_date or date(2026, 4, 25),
        regime=regime,
        market_score=65,
        spy_trend_score=20,
        qqq_trend_score=15,
        iwm_breadth_score=10,
        sector_participation_score=8,
        risk_appetite_score=8,
        volatility_stress_score=8,
        allowed_exposure_pct=70.0,
        single_trade_risk_pct=cap,
        preferred_setups='["BREAKOUT","PULLBACK"]',
        avoid_setups='["EXTENDED"]',
        computed_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.flush()
    return row


def _seed_user_settings(
    db,
    account_size: float = 100000.0,
    single_trade_risk_pct: float = 1.0,
) -> UserSettings:
    row = UserSettings(
        id=1,
        account_size=account_size,
        max_exposure_pct=80.0,
        single_trade_risk_pct=single_trade_risk_pct,
        default_risk_per_trade_pct=0.75,
        base_currency="USD",
        updated_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.flush()
    return row


def _seed_earnings(db, ticker: str, days_from_today: int) -> EarningsEvent:
    row = EarningsEvent(
        ticker=ticker,
        earnings_date=date.today() + timedelta(days=days_from_today),
        fetched_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.flush()
    return row


# ─── S1: Baseline position sizing ─────────────────────────────────────────────


class TestS1BaselinePositionSizing:
    """S1: BREAKOUT entry=850 stop=820, user 100k/1%, regime CONSTRUCTIVE 1% → 33 shares."""

    def test_suggested_shares(self, db_session):
        _seed_snapshot(db_session)
        _seed_regime(db_session)
        _seed_user_settings(db_session)
        db_session.commit()

        result = compute_decision(db_session, "NVDA")

        assert result.suggested_shares == 33
        assert math.isclose(result.position_value, 28050.0)
        assert math.isclose(result.target_2r, 910.0)
        assert math.isclose(result.target_3r, 940.0)
        assert math.isclose(result.risk_per_share, 30.0)
        assert math.isclose(result.effective_risk_pct, 1.0)
        assert math.isclose(result.regime_cap, 1.0)
        assert math.isclose(result.user_setting_cap, 1.0)

    def test_account_risk_pct_le_effective(self, db_session):
        """accountRiskPct must be ≤ effectiveRiskPct (floor rounding)."""
        _seed_snapshot(db_session)
        _seed_regime(db_session)
        _seed_user_settings(db_session)
        db_session.commit()

        result = compute_decision(db_session, "NVDA")

        assert result.account_risk_pct <= result.effective_risk_pct


# ─── S2: risk_pct override direction ──────────────────────────────────────────


class TestS2RiskPctOverride:
    """S2: override can narrow effective risk but cannot widen it."""

    def _base(self, db):
        _seed_snapshot(db)
        _seed_regime(db)
        _seed_user_settings(db, single_trade_risk_pct=1.0)
        db.commit()

    def test_override_narrows(self, db_session):
        self._base(db_session)
        result = compute_decision(db_session, "NVDA", risk_pct_override=0.5)
        assert math.isclose(result.effective_risk_pct, 0.5)

    def test_override_cannot_widen(self, db_session):
        self._base(db_session)
        result = compute_decision(db_session, "NVDA", risk_pct_override=5.0)
        # min(regime=1.0, user=1.0, override=5.0) → 1.0
        assert math.isclose(result.effective_risk_pct, 1.0)


# ─── S3: RISK_OFF → zero shares ───────────────────────────────────────────────


class TestS3RiskOff:
    """S3: regime=RISK_OFF single_trade_risk_pct=0 → suggestedShares=0 (no error)."""

    def test_risk_off_zeroes_position(self, db_session):
        _seed_snapshot(db_session)
        _seed_regime(db_session, regime="RISK_OFF", single_trade_risk_pct=0.0)
        _seed_user_settings(db_session)
        db_session.commit()

        result = compute_decision(db_session, "NVDA")

        assert result.suggested_shares == 0
        assert result.position_value == 0.0
        assert result.account_risk_pct == 0.0
        assert math.isclose(result.effective_risk_pct, 0.0)


# ─── S4: Earnings risk classification ─────────────────────────────────────────


class TestS4EarningsRisk:
    """S4: earningsRisk tiers and null case."""

    def _setup(self, db):
        _seed_snapshot(db)
        _seed_regime(db)
        _seed_user_settings(db)

    def test_danger(self, db_session):
        self._setup(db_session)
        _seed_earnings(db_session, "NVDA", days_from_today=2)
        db_session.commit()
        result = compute_decision(db_session, "NVDA")
        assert result.earnings_risk == "DANGER"
        assert result.earnings_date is not None

    def test_caution(self, db_session):
        self._setup(db_session)
        _seed_earnings(db_session, "NVDA", days_from_today=8)
        db_session.commit()
        result = compute_decision(db_session, "NVDA")
        assert result.earnings_risk == "CAUTION"

    def test_safe(self, db_session):
        self._setup(db_session)
        _seed_earnings(db_session, "NVDA", days_from_today=30)
        db_session.commit()
        result = compute_decision(db_session, "NVDA")
        assert result.earnings_risk == "SAFE"

    def test_no_earnings_returns_null(self, db_session):
        self._setup(db_session)
        db_session.commit()
        result = compute_decision(db_session, "NVDA")
        assert result.earnings_risk is None
        assert result.earnings_date is None

    def test_danger_boundary(self, db_session):
        """days = EARNINGS_DANGER_DAYS exactly → DANGER."""
        self._setup(db_session)
        _seed_earnings(db_session, "NVDA", days_from_today=SETUP.EARNINGS_DANGER_DAYS)
        db_session.commit()
        result = compute_decision(db_session, "NVDA")
        assert result.earnings_risk == "DANGER"

    def test_caution_boundary(self, db_session):
        """days = EARNINGS_CAUTION_DAYS exactly → CAUTION."""
        self._setup(db_session)
        _seed_earnings(db_session, "NVDA", days_from_today=SETUP.EARNINGS_CAUTION_DAYS)
        db_session.commit()
        result = compute_decision(db_session, "NVDA")
        assert result.earnings_risk == "CAUTION"


# ─── S5: deterministicHash reproducibility ────────────────────────────────────


class TestS5DeterministicHash:
    """S5: same inputs → same hash; 1-cent entry change → different hash."""

    def _setup(self, db):
        _seed_snapshot(db)
        _seed_regime(db)
        _seed_user_settings(db)
        db.commit()

    def test_hash_is_reproducible(self, db_session):
        self._setup(db_session)
        r1 = compute_decision(db_session, "NVDA")
        r2 = compute_decision(db_session, "NVDA")
        assert r1.deterministic_hash == r2.deterministic_hash

    def test_hash_changes_with_entry(self, db_session):
        self._setup(db_session)
        r_base = compute_decision(db_session, "NVDA")
        r_diff = compute_decision(db_session, "NVDA", entry_override=850.01)
        assert r_base.deterministic_hash != r_diff.deterministic_hash

    def test_hash_length(self, db_session):
        self._setup(db_session)
        result = compute_decision(db_session, "NVDA")
        assert len(result.deterministic_hash) == DECISION.HASH_DIGEST_LENGTH

    def test_hash_formula(self, db_session):
        """Verify hash matches expected SHA-256 formula manually."""
        self._setup(db_session)
        result = compute_decision(db_session, "NVDA")
        snapshot_date = date(2026, 4, 25)
        preimage = f"NVDA|850.00|820.00|{result.effective_risk_pct:.4f}|{snapshot_date.isoformat()}"
        expected = hashlib.sha256(preimage.encode()).hexdigest()[:16]
        assert result.deterministic_hash == expected


# ─── S6: entry ≤ stop validation ──────────────────────────────────────────────


class TestS6EntryStopValidation:
    """S6: override producing entry ≤ stop raises ValueError."""

    def test_entry_equal_stop_raises(self, db_session):
        _seed_snapshot(db_session)
        _seed_regime(db_session)
        _seed_user_settings(db_session)
        db_session.commit()
        with pytest.raises(ValueError):
            compute_decision(db_session, "NVDA", entry_override=820.0, stop_override=820.0)

    def test_entry_less_than_stop_raises(self, db_session):
        _seed_snapshot(db_session)
        _seed_regime(db_session)
        _seed_user_settings(db_session)
        db_session.commit()
        with pytest.raises(ValueError):
            compute_decision(db_session, "NVDA", entry_override=810.0, stop_override=820.0)


# ─── S7: fallback defaults ────────────────────────────────────────────────────


class TestS7Fallbacks:
    """S7: user_settings absent → defaults; market_regime_snapshots empty → NEUTRAL cap."""

    def test_no_user_settings_uses_defaults(self, db_session):
        _seed_snapshot(db_session)
        _seed_regime(db_session, single_trade_risk_pct=1.0)
        # no user_settings row
        db_session.commit()
        result = compute_decision(db_session, "NVDA")
        assert math.isclose(result.user_setting_cap, DECISION.DEFAULT_SINGLE_TRADE_RISK_PCT)

    def test_empty_regime_table_uses_neutral_cap(self, db_session):
        _seed_snapshot(db_session)
        _seed_user_settings(db_session)
        # no market_regime_snapshots row
        db_session.commit()
        result = compute_decision(db_session, "NVDA")
        neutral_cap = REGIME.SINGLE_TRADE_RISK_PCT[DECISION.REGIME_FALLBACK]
        assert math.isclose(result.regime_cap, neutral_cap)


# ─── S8–S12: Router integration tests ────────────────────────────────────────


_REQUIRED_CAMEL_FIELDS = {
    "ticker",
    "setupType",
    "setupQuality",
    "entryPrice",
    "stopPrice",
    "target2r",
    "target3r",
    "rewardRisk",
    "riskPerShare",
    "suggestedShares",
    "positionValue",
    "accountRiskPct",
    "effectiveRiskPct",
    "regimeCap",
    "userSettingCap",
    "earningsRisk",
    "earningsDate",
    "deterministicHash",
}


def _seed_all(db):
    _seed_snapshot(db)
    _seed_regime(db)
    _seed_user_settings(db)
    db.commit()


class TestS8RouterBasic:
    """S8: GET /api/cockpit/decision/NVDA → 200 with full camelCase envelope."""

    def test_200_envelope_and_fields(self, client, db_session):
        _seed_all(db_session)
        resp = client.get("/api/cockpit/decision/NVDA")
        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "success"
        data = body["data"]
        assert data["ticker"] == "NVDA"
        missing = _REQUIRED_CAMEL_FIELDS - data.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_numeric_fields_are_numbers(self, client, db_session):
        _seed_all(db_session)
        resp = client.get("/api/cockpit/decision/NVDA")
        data = resp.json()["data"]
        assert isinstance(data["entryPrice"], (int, float))
        assert isinstance(data["suggestedShares"], int)
        assert isinstance(data["positionValue"], (int, float))


class TestS9RouterOverride:
    """S9: query override params propagate through full stack."""

    def test_full_override(self, client, db_session):
        _seed_all(db_session)
        resp = client.get(
            "/api/cockpit/decision/NVDA"
            "?entryOverride=900&stopOverride=860&riskPctOverride=0.5"
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert math.isclose(data["entryPrice"], 900.0)
        assert math.isclose(data["stopPrice"], 860.0)
        # effective = min(regime=1.0, user=1.0, override=0.5) = 0.5
        assert math.isclose(data["effectiveRiskPct"], 0.5)

    def test_override_cannot_widen_risk(self, client, db_session):
        _seed_all(db_session)
        resp = client.get("/api/cockpit/decision/NVDA?riskPctOverride=5.0")
        assert resp.status_code == 200
        data = resp.json()["data"]
        # regime cap = 1.0, override=5.0 → effective still 1.0
        assert math.isclose(data["effectiveRiskPct"], 1.0)


class TestS10RouterNotFound:
    """S10: unknown ticker with no snapshot → 404 NOT_FOUND."""

    def test_unknown_ticker_404(self, client):
        resp = client.get("/api/cockpit/decision/UNKNOWN_XYZ")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "NOT_FOUND"


class TestS11RouterValidationError:
    """S11: entry ≤ stop override → 422 VALIDATION_ERROR."""

    def test_entry_equal_stop_422(self, client, db_session):
        _seed_all(db_session)
        resp = client.get("/api/cockpit/decision/NVDA?entryOverride=820&stopOverride=820")
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_entry_below_stop_422(self, client, db_session):
        _seed_all(db_session)
        resp = client.get("/api/cockpit/decision/NVDA?entryOverride=800&stopOverride=820")
        assert resp.status_code == 422


class TestS12TickerCaseNormalization:
    """S12: lowercase ticker 'nvda' matches 'NVDA' snapshot."""

    def test_lowercase_ticker_matches(self, client, db_session):
        _seed_all(db_session)
        resp = client.get("/api/cockpit/decision/nvda")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["ticker"] == "NVDA"

    def test_mixed_case_ticker_matches(self, client, db_session):
        _seed_all(db_session)
        resp = client.get("/api/cockpit/decision/NvDa")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["ticker"] == "NVDA"
