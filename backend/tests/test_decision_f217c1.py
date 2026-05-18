"""F217-c1: capitulationEvidence backend wiring tests.

T1-T4: pure unit tests (schema + helper).
T5-T8: integration tests seeding real db_session (added in Step 5).
"""

from __future__ import annotations

import pytest

from app.schemas.cockpit.decision import CapitulationEvidence, DecisionData
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


# ─── T5-T8: integration tests (added in Step 5) ──────────────────────────────
# Placeholder — will be filled after Step 4 (decision_service wiring)
