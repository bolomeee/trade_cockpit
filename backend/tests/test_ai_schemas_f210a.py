"""F210-a: AI schema unit tests — candidate_ranker + trade_plan.

§I  — CandidateRankerInput constraints (I1-I9)
§O  — CandidateRankerOutput constraints (O1-O6)
§TI — TradePlanInput constraints (TI1-TI4)
§G  — trade_plan guardrail (G1-G7)
§R  — REGISTRY + routing tier (R1-R5)
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.ai.errors import AiGuardrailViolation
from app.ai.schemas.candidate_ranker import (
    CandidateRankerInput,
    CandidateRankerOutput,
)
from app.ai.schemas.trade_plan import TradePlanInput, TradePlanOutput, guardrail

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_CANDIDATE_VALID = {
    "ticker": "AAPL",
    "setupType": "BREAKOUT",
    "setupQuality": "A",
    "trendScore": 4,
    "rsPercentile": 85.0,
    "distanceToEntryPct": 1.5,
    "rewardRisk": 2.5,
    "earningsRisk": "SAFE",
    "readySignal": True,
}

_RANKER_INPUT_VALID = {
    "regime": "CONSTRUCTIVE",
    "regimeScore": 72,
    "candidates": [_CANDIDATE_VALID],
}

_RANKER_OUTPUT_VALID = {
    "topCandidates": [
        {"ticker": "AAPL", "rank": 1, "reason": "Strong RS with tight consolidation.", "action": "enter"},
        {"ticker": "MSFT", "rank": 2, "reason": "Solid trend pulling back to support.", "action": "watch"},
        {"ticker": "NVDA", "rank": 3, "reason": "Extended but high RS worth watching.", "action": "wait"},
    ]
}

_TRADE_PLAN_INPUT_VALID = {
    "ticker": "AAPL",
    "setupType": "BREAKOUT",
    "setupQuality": "A",
    "entry": 182.50,
    "stop": 178.00,
    "target2r": 191.50,
    "target3r": 196.00,
    "size": 55,
    "rewardRisk": 2.0,
    "accountRiskPct": 1.0,
    "earningsRisk": "SAFE",
    "deterministicHash": "abcd1234",
}

_TRADE_PLAN_OUTPUT_VALID = {
    "memo": "AAPL sets up in a clean breakout above the pivot. RS is strong and earnings risk is SAFE. Trail stop with 21EMA after 2R achieved.",
    "management": ["Hold through initial volatility", "Move stop to BE near 2R", "Trail with 21EMA"],
    "entry": 182.50,
    "stop": 178.00,
    "size": 55,
}


# ---------------------------------------------------------------------------
# §I — CandidateRankerInput
# ---------------------------------------------------------------------------


class TestCandidateRankerInput:
    def test_I1_single_candidate_min_boundary(self):
        """min_length=1: one candidate is valid."""
        obj = CandidateRankerInput(**_RANKER_INPUT_VALID)
        assert len(obj.candidates) == 1

    def test_I2_twenty_candidates_max_boundary(self):
        """max_length=20: exactly 20 candidates passes."""
        data = {**_RANKER_INPUT_VALID, "candidates": [_CANDIDATE_VALID] * 20}
        obj = CandidateRankerInput(**data)
        assert len(obj.candidates) == 20

    def test_I3_twenty_one_candidates_rejected(self):
        """21 candidates → ValidationError (max_length=20)."""
        data = {**_RANKER_INPUT_VALID, "candidates": [_CANDIDATE_VALID] * 21}
        with pytest.raises(ValidationError):
            CandidateRankerInput(**data)

    def test_I4_zero_candidates_rejected(self):
        """Empty candidates list → ValidationError (min_length=1)."""
        data = {**_RANKER_INPUT_VALID, "candidates": []}
        with pytest.raises(ValidationError):
            CandidateRankerInput(**data)

    def test_I5_invalid_regime_rejected(self):
        """Non-enum regime → ValidationError."""
        data = {**_RANKER_INPUT_VALID, "regime": "BULLISH"}
        with pytest.raises(ValidationError):
            CandidateRankerInput(**data)

    def test_I5b_all_five_regime_values_accepted(self):
        """Regime literal must accept the 5 values returned by market_regime_service:
        RISK_ON / CONSTRUCTIVE / NEUTRAL / DEFENSIVE / RISK_OFF."""
        for regime in ("RISK_ON", "CONSTRUCTIVE", "NEUTRAL", "DEFENSIVE", "RISK_OFF"):
            obj = CandidateRankerInput(**{**_RANKER_INPUT_VALID, "regime": regime})
            assert obj.regime == regime

    def test_I6_trend_score_out_of_range(self):
        """trendScore=6 → ValidationError (le=5)."""
        bad_candidate = {**_CANDIDATE_VALID, "trendScore": 6}
        data = {**_RANKER_INPUT_VALID, "candidates": [bad_candidate]}
        with pytest.raises(ValidationError):
            CandidateRankerInput(**data)

    def test_I7_rs_percentile_over_100(self):
        """rsPercentile=101 → ValidationError (le=100)."""
        bad_candidate = {**_CANDIDATE_VALID, "rsPercentile": 101.0}
        data = {**_RANKER_INPUT_VALID, "candidates": [bad_candidate]}
        with pytest.raises(ValidationError):
            CandidateRankerInput(**data)

    def test_I8_invalid_setup_type(self):
        """Non-enum setupType → ValidationError."""
        bad_candidate = {**_CANDIDATE_VALID, "setupType": "MOONSHOT"}
        data = {**_RANKER_INPUT_VALID, "candidates": [bad_candidate]}
        with pytest.raises(ValidationError):
            CandidateRankerInput(**data)

    def test_I9_extra_field_rejected(self):
        """extra=forbid: unknown field at top level → ValidationError."""
        data = {**_RANKER_INPUT_VALID, "unknownField": "oops"}
        with pytest.raises(ValidationError):
            CandidateRankerInput(**data)


# ---------------------------------------------------------------------------
# §O — CandidateRankerOutput
# ---------------------------------------------------------------------------


class TestCandidateRankerOutput:
    def test_O1_three_ranked_candidates_valid(self):
        """Exactly 3 candidates with ranks 1/2/3 → passes."""
        obj = CandidateRankerOutput(**_RANKER_OUTPUT_VALID)
        assert len(obj.topCandidates) == 3

    def test_O2_two_candidates_rejected(self):
        """2 candidates → ValidationError (min_length=3)."""
        data = {"topCandidates": _RANKER_OUTPUT_VALID["topCandidates"][:2]}
        with pytest.raises(ValidationError):
            CandidateRankerOutput(**data)

    def test_O3_four_candidates_rejected(self):
        """4 candidates → ValidationError (max_length=3)."""
        extra = {"ticker": "GOOG", "rank": 1, "reason": "Extra.", "action": "wait"}
        data = {"topCandidates": [*_RANKER_OUTPUT_VALID["topCandidates"], extra]}
        with pytest.raises(ValidationError):
            CandidateRankerOutput(**data)

    def test_O4_rank_four_rejected(self):
        """rank=4 → ValidationError (Literal[1,2,3])."""
        bad = [
            {"ticker": "AAPL", "rank": 4, "reason": "Test.", "action": "enter"},
            {"ticker": "MSFT", "rank": 2, "reason": "Test.", "action": "watch"},
            {"ticker": "NVDA", "rank": 3, "reason": "Test.", "action": "wait"},
        ]
        with pytest.raises(ValidationError):
            CandidateRankerOutput(topCandidates=bad)

    def test_O5_invalid_action_rejected(self):
        """Non-enum action → ValidationError."""
        bad = [
            {"ticker": "AAPL", "rank": 1, "reason": "Test.", "action": "buy"},
            {"ticker": "MSFT", "rank": 2, "reason": "Test.", "action": "watch"},
            {"ticker": "NVDA", "rank": 3, "reason": "Test.", "action": "wait"},
        ]
        with pytest.raises(ValidationError):
            CandidateRankerOutput(topCandidates=bad)

    def test_O6_reason_over_200_chars_rejected(self):
        """reason > 200 chars → ValidationError (max_length=200)."""
        long_reason = "A" * 201
        bad = [
            {"ticker": "AAPL", "rank": 1, "reason": long_reason, "action": "enter"},
            {"ticker": "MSFT", "rank": 2, "reason": "Test.", "action": "watch"},
            {"ticker": "NVDA", "rank": 3, "reason": "Test.", "action": "wait"},
        ]
        with pytest.raises(ValidationError):
            CandidateRankerOutput(topCandidates=bad)


# ---------------------------------------------------------------------------
# §TI — TradePlanInput
# ---------------------------------------------------------------------------


class TestTradePlanInput:
    def test_TI1_full_valid_input(self):
        """All 12 fields within constraints → passes."""
        obj = TradePlanInput(**_TRADE_PLAN_INPUT_VALID)
        assert obj.ticker == "AAPL"
        assert obj.size == 55

    def test_TI2_entry_zero_rejected(self):
        """entry=0 → ValidationError (gt=0)."""
        data = {**_TRADE_PLAN_INPUT_VALID, "entry": 0}
        with pytest.raises(ValidationError):
            TradePlanInput(**data)

    def test_TI3_size_zero_rejected(self):
        """size=0 → ValidationError (ge=1)."""
        data = {**_TRADE_PLAN_INPUT_VALID, "size": 0}
        with pytest.raises(ValidationError):
            TradePlanInput(**data)

    def test_TI4_deterministic_hash_too_short(self):
        """deterministicHash with 7 chars → ValidationError (min_length=8)."""
        data = {**_TRADE_PLAN_INPUT_VALID, "deterministicHash": "short7c"}
        with pytest.raises(ValidationError):
            TradePlanInput(**data)

    def test_TI5_earnings_risk_null_accepted(self):
        """earningsRisk=None passes (no earnings data — common for non-US-equity tickers)."""
        data = {**_TRADE_PLAN_INPUT_VALID, "earningsRisk": None}
        obj = TradePlanInput(**data)
        assert obj.earningsRisk is None


# ---------------------------------------------------------------------------
# §G — trade_plan guardrail
# ---------------------------------------------------------------------------


class TestTradePlanGuardrail:
    def test_G1_matching_entry_stop_size_passes(self):
        """Output mirrors input → guardrail passes silently."""
        guardrail(_TRADE_PLAN_INPUT_VALID, _TRADE_PLAN_OUTPUT_VALID)

    def test_G2_entry_off_by_cent_raises(self):
        """output.entry differs by 0.01 → AiGuardrailViolation (entry)."""
        bad_out = {**_TRADE_PLAN_OUTPUT_VALID, "entry": 182.51}
        with pytest.raises(AiGuardrailViolation, match="entry"):
            guardrail(_TRADE_PLAN_INPUT_VALID, bad_out)

    def test_G3_stop_off_by_cent_raises(self):
        """output.stop differs by 0.01 → AiGuardrailViolation (stop)."""
        bad_out = {**_TRADE_PLAN_OUTPUT_VALID, "stop": 177.99}
        with pytest.raises(AiGuardrailViolation, match="stop"):
            guardrail(_TRADE_PLAN_INPUT_VALID, bad_out)

    def test_G4_size_plus_one_raises(self):
        """output.size = input.size+1 → AiGuardrailViolation (size)."""
        bad_out = {**_TRADE_PLAN_OUTPUT_VALID, "size": 56}
        with pytest.raises(AiGuardrailViolation, match="size"):
            guardrail(_TRADE_PLAN_INPUT_VALID, bad_out)

    def test_G5_sub_decimal_difference_rounds_equal(self):
        """output.entry=182.001 rounds to 182.00 = input 182.00 → passes."""
        inp = {**_TRADE_PLAN_INPUT_VALID, "entry": 182.00}
        out = {**_TRADE_PLAN_OUTPUT_VALID, "entry": 182.001}
        guardrail(inp, out)

    def test_G6_banned_phrase_in_memo_raises(self):
        """memo contains 'buy now' → AiGuardrailViolation (banned phrase)."""
        bad_out = {**_TRADE_PLAN_OUTPUT_VALID, "memo": "You should buy now at entry."}
        with pytest.raises(AiGuardrailViolation, match="banned phrase"):
            guardrail(_TRADE_PLAN_INPUT_VALID, bad_out)

    def test_G7_banned_phrase_in_management_raises(self):
        """management item contains 'ignore stop' → AiGuardrailViolation."""
        bad_out = {**_TRADE_PLAN_OUTPUT_VALID, "management": ["ignore stop loss if price drops"]}
        with pytest.raises(AiGuardrailViolation, match="banned phrase"):
            guardrail(_TRADE_PLAN_INPUT_VALID, bad_out)


# ---------------------------------------------------------------------------
# §R — REGISTRY + routing tier
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_R1_get_schemas_candidate_ranker(self):
        """get_schemas('candidate_ranker') returns a SchemaPair."""
        from app.ai.schemas import get_schemas, SchemaPair

        pair = get_schemas("candidate_ranker")
        assert isinstance(pair, SchemaPair)
        assert pair.input_schema is CandidateRankerInput
        assert pair.output_schema is CandidateRankerOutput

    def test_R2_get_schemas_trade_plan(self):
        """get_schemas('trade_plan') returns a SchemaPair."""
        from app.ai.schemas import get_schemas, SchemaPair
        from app.ai.schemas.trade_plan import TradePlanInput, TradePlanOutput

        pair = get_schemas("trade_plan")
        assert isinstance(pair, SchemaPair)
        assert pair.input_schema is TradePlanInput
        assert pair.output_schema is TradePlanOutput

    def test_R3_trade_plan_guardrail_registered(self):
        """guardrail._HOOKS['trade_plan'] is populated after module load."""
        from app.ai import guardrail as gr

        assert "trade_plan" in gr._HOOKS
        assert callable(gr._HOOKS["trade_plan"])

    def test_R4_candidate_ranker_guardrail_not_registered(self):
        """candidate_ranker has no guardrail hook (no deterministic anchor)."""
        from app.ai import guardrail as gr

        assert gr._HOOKS.get("candidate_ranker") is None

    def test_R5_both_tasks_resolve_critical_tier(self):
        """routing.resolve_tier returns 'critical' for candidate_ranker and trade_plan."""
        from app.ai.routing import resolve_tier

        assert resolve_tier("candidate_ranker") == "critical"
        assert resolve_tier("trade_plan") == "critical"
