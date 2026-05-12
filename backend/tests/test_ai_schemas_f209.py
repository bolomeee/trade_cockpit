"""F209-a: AI schema registration tests (market_narrator + setup_explainer).

§A — Schema field constraints (pure Pydantic unit tests, no gateway/db)
§B — REGISTRY registration validation
§C — Guardrail registration side effect + 6 banned phrase hits
§D — Endpoint end-to-end (mock LiteLLM + TestClient)
§E — Live smoke (@pytest.mark.live, skipped when OPENAI_API_KEY absent)
"""
from __future__ import annotations

import inspect
import os
from decimal import Decimal

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_MN_INPUT_VALID = {
    "regime": "CONSTRUCTIVE",
    "marketScore": 72,
    "subscores": {
        "spyTrend": 80,
        "qqqTrend": 75,
        "iwmBreadth": 60,
        "sectorParticipation": 70,
        "riskAppetite": 65,
        "volatilityStress": 30,
    },
    "sectors": [
        {"symbol": "XLK", "closePct": 1.2, "state": "Strong"},
        {"symbol": "XLE", "closePct": -0.5, "state": "Weak"},
    ],
}

_MN_OUTPUT_VALID = {
    "headline": "Constructive tape with tech leadership",
    "summary": "Market internals remain supportive with broad sector participation.",
    "riskPosture": "balanced",
    "preferredSetups": ["pullback", "breakout"],
    "avoid": ["reversal"],
    "warnings": ["macro event risk next week"],
}

_SE_INPUT_VALID = {
    "ticker": "AAPL",
    "trend": "up",
    "rs": 85.5,
    "setup": "pullback",
    "risk": {"entry": 182.50, "stop": 178.00},
}

_SE_OUTPUT_VALID = {
    "label": "High RS pullback to 21-day EMA",
    "quality": "A",
    "whyWatch": "Strong relative strength name pulling back to support with volume drying up.",
    "mainRisks": ["broader market weakness", "failed breakout risk"],
}


# ---------------------------------------------------------------------------
# §A — Schema field constraints
# ---------------------------------------------------------------------------


class TestSchemaConstraints:
    # --- MarketNarratorInput ---

    def test_A1_mn_input_valid_example(self):
        from app.ai.schemas.market_narrator import MarketNarratorInput

        obj = MarketNarratorInput(**_MN_INPUT_VALID)
        assert obj.regime == "CONSTRUCTIVE"
        assert obj.marketScore == 72
        assert obj.subscores.spyTrend == 80
        assert len(obj.sectors) == 2

    def test_A2_mn_input_extra_field_rejected(self):
        from app.ai.schemas.market_narrator import MarketNarratorInput

        with pytest.raises(ValidationError):
            MarketNarratorInput(**{**_MN_INPUT_VALID, "extraField": "bad"})

    def test_A3_mn_input_market_score_below_zero(self):
        from app.ai.schemas.market_narrator import MarketNarratorInput

        with pytest.raises(ValidationError):
            MarketNarratorInput(**{**_MN_INPUT_VALID, "marketScore": -1})

    def test_A4_mn_input_market_score_above_100(self):
        from app.ai.schemas.market_narrator import MarketNarratorInput

        with pytest.raises(ValidationError):
            MarketNarratorInput(**{**_MN_INPUT_VALID, "marketScore": 101})

    def test_A5_mn_input_regime_invalid(self):
        from app.ai.schemas.market_narrator import MarketNarratorInput

        with pytest.raises(ValidationError):
            MarketNarratorInput(**{**_MN_INPUT_VALID, "regime": "BULLISH"})

    def test_A6_mn_subscores_extra_field_rejected(self):
        from app.ai.schemas.market_narrator import MarketNarratorInput

        bad = {**_MN_INPUT_VALID}
        bad["subscores"] = {**_MN_INPUT_VALID["subscores"], "extraScore": 99}
        with pytest.raises(ValidationError):
            MarketNarratorInput(**bad)

    def test_A7_mn_sector_invalid_state(self):
        from app.ai.schemas.market_narrator import MarketNarratorInput

        bad = {**_MN_INPUT_VALID}
        bad["sectors"] = [{"symbol": "XLK", "closePct": 1.0, "state": "Bullish"}]
        with pytest.raises(ValidationError):
            MarketNarratorInput(**bad)

    # --- MarketNarratorOutput ---

    def test_A8_mn_output_valid(self):
        from app.ai.schemas.market_narrator import MarketNarratorOutput

        obj = MarketNarratorOutput(**_MN_OUTPUT_VALID)
        assert obj.riskPosture == "balanced"
        assert len(obj.preferredSetups) == 2

    def test_A9_mn_output_headline_empty_rejected(self):
        from app.ai.schemas.market_narrator import MarketNarratorOutput

        with pytest.raises(ValidationError):
            MarketNarratorOutput(**{**_MN_OUTPUT_VALID, "headline": ""})

    def test_A10_mn_output_risk_posture_invalid(self):
        from app.ai.schemas.market_narrator import MarketNarratorOutput

        with pytest.raises(ValidationError):
            MarketNarratorOutput(**{**_MN_OUTPUT_VALID, "riskPosture": "bullish"})

    def test_A11_mn_output_extra_field_rejected(self):
        from app.ai.schemas.market_narrator import MarketNarratorOutput

        with pytest.raises(ValidationError):
            MarketNarratorOutput(**{**_MN_OUTPUT_VALID, "extra": "nope"})

    def test_A12_mn_output_preferred_setups_too_many(self):
        from app.ai.schemas.market_narrator import MarketNarratorOutput

        with pytest.raises(ValidationError):
            MarketNarratorOutput(
                **{**_MN_OUTPUT_VALID, "preferredSetups": ["a", "b", "c", "d", "e", "f"]}
            )

    # --- SetupExplainerInput ---

    def test_A13_se_input_valid_example(self):
        from app.ai.schemas.setup_explainer import SetupExplainerInput

        obj = SetupExplainerInput(**_SE_INPUT_VALID)
        assert obj.ticker == "AAPL"
        assert obj.setup == "pullback"
        assert obj.risk.entry == 182.50

    def test_A14_se_input_ticker_lowercase_rejected(self):
        from app.ai.schemas.setup_explainer import SetupExplainerInput

        with pytest.raises(ValidationError):
            SetupExplainerInput(**{**_SE_INPUT_VALID, "ticker": "aapl"})

    def test_A15_se_input_risk_entry_zero_rejected(self):
        from app.ai.schemas.setup_explainer import SetupExplainerInput

        bad = {**_SE_INPUT_VALID, "risk": {"entry": 0.0, "stop": 178.00}}
        with pytest.raises(ValidationError):
            SetupExplainerInput(**bad)

    def test_A16_se_input_risk_stop_negative_rejected(self):
        from app.ai.schemas.setup_explainer import SetupExplainerInput

        bad = {**_SE_INPUT_VALID, "risk": {"entry": 182.50, "stop": -1.0}}
        with pytest.raises(ValidationError):
            SetupExplainerInput(**bad)

    def test_A17_se_input_extra_field_rejected(self):
        from app.ai.schemas.setup_explainer import SetupExplainerInput

        with pytest.raises(ValidationError):
            SetupExplainerInput(**{**_SE_INPUT_VALID, "bogus": True})

    def test_A18_se_input_setup_invalid(self):
        from app.ai.schemas.setup_explainer import SetupExplainerInput

        with pytest.raises(ValidationError):
            SetupExplainerInput(**{**_SE_INPUT_VALID, "setup": "momentum"})

    # --- SetupExplainerOutput ---

    def test_A19_se_output_valid(self):
        from app.ai.schemas.setup_explainer import SetupExplainerOutput

        obj = SetupExplainerOutput(**_SE_OUTPUT_VALID)
        assert obj.quality == "A"
        assert len(obj.mainRisks) == 2

    def test_A20_se_output_quality_invalid(self):
        from app.ai.schemas.setup_explainer import SetupExplainerOutput

        with pytest.raises(ValidationError):
            SetupExplainerOutput(**{**_SE_OUTPUT_VALID, "quality": "E"})

    def test_A21_se_output_main_risks_empty_rejected(self):
        from app.ai.schemas.setup_explainer import SetupExplainerOutput

        with pytest.raises(ValidationError):
            SetupExplainerOutput(**{**_SE_OUTPUT_VALID, "mainRisks": []})

    def test_A22_se_output_extra_field_rejected(self):
        from app.ai.schemas.setup_explainer import SetupExplainerOutput

        with pytest.raises(ValidationError):
            SetupExplainerOutput(**{**_SE_OUTPUT_VALID, "extra": "nope"})

    def test_A23_no_litellm_import_in_schema_modules(self):
        """Completion criterion #13: schema modules must not top-level import litellm."""
        import app.ai.schemas.market_narrator as mn
        import app.ai.schemas.setup_explainer as se

        for mod in (mn, se):
            src = inspect.getsource(mod)
            # Top-level import litellm would appear as "import litellm" or "from litellm"
            # We check it doesn't appear outside of string literals at all
            assert "import litellm" not in src, f"{mod.__name__} must not import litellm"
            assert "from litellm" not in src, f"{mod.__name__} must not from-import litellm"


# ---------------------------------------------------------------------------
# §B — Registry registration
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_B1_market_narrator_in_registry(self):
        from app.ai.schemas import REGISTRY

        assert "market_narrator" in REGISTRY

    def test_B2_market_narrator_get_schemas(self):
        from app.ai.schemas import get_schemas
        from app.ai.schemas.market_narrator import MarketNarratorInput, MarketNarratorOutput

        pair = get_schemas("market_narrator")
        assert pair.input_schema is MarketNarratorInput
        assert pair.output_schema is MarketNarratorOutput

    def test_B3_setup_explainer_in_registry(self):
        from app.ai.schemas import REGISTRY

        assert "setup_explainer" in REGISTRY

    def test_B4_setup_explainer_get_schemas(self):
        from app.ai.schemas import get_schemas
        from app.ai.schemas.setup_explainer import SetupExplainerInput, SetupExplainerOutput

        pair = get_schemas("setup_explainer")
        assert pair.input_schema is SetupExplainerInput
        assert pair.output_schema is SetupExplainerOutput

    def test_B5_echo_still_present(self):
        from app.ai.schemas import REGISTRY

        assert "echo" in REGISTRY

    def test_B6_unknown_task_raises_key_error(self):
        from app.ai.schemas import get_schemas

        with pytest.raises(KeyError):
            get_schemas("nonexistent_task")


# ---------------------------------------------------------------------------
# §C — Guardrail registration side effect + banned phrase hits
# ---------------------------------------------------------------------------


class TestGuardrail:
    def test_C1_market_narrator_hook_registered(self):
        from app.ai import guardrail as gr
        from app.ai.schemas import market_narrator as mn
        # Importing REGISTRY triggers guardrail registration
        from app.ai.schemas import REGISTRY  # noqa: F401

        assert gr._HOOKS["market_narrator"] is mn.guardrail

    def test_C2_setup_explainer_hook_registered(self):
        from app.ai import guardrail as gr
        from app.ai.schemas import setup_explainer as se
        from app.ai.schemas import REGISTRY  # noqa: F401

        assert gr._HOOKS["setup_explainer"] is se.guardrail

    def test_C3_guardrail_hits_buy_now(self):
        from app.ai.errors import AiGuardrailViolation
        from app.ai.schemas.market_narrator import guardrail

        bad_output = {
            "headline": "go buy now!",
            "summary": "Everything looks great.",
            "riskPosture": "aggressive",
            "preferredSetups": [],
            "avoid": [],
            "warnings": [],
        }
        with pytest.raises(AiGuardrailViolation, match="buy now"):
            guardrail({}, bad_output)

    def test_C4_guardrail_hits_sell_now(self):
        from app.ai.errors import AiGuardrailViolation
        from app.ai.schemas.market_narrator import guardrail

        bad_output = {**_MN_OUTPUT_VALID, "summary": "You should sell now immediately."}
        with pytest.raises(AiGuardrailViolation, match="sell now"):
            guardrail({}, bad_output)

    def test_C5_guardrail_hits_guaranteed_return_zh(self):
        from app.ai.errors import AiGuardrailViolation
        from app.ai.schemas.market_narrator import guardrail

        bad_output = {**_MN_OUTPUT_VALID, "summary": "我们承诺收益翻倍"}
        with pytest.raises(AiGuardrailViolation, match="承诺收益"):
            guardrail({}, bad_output)

    def test_C6_guardrail_hits_guaranteed_profit_zh(self):
        from app.ai.errors import AiGuardrailViolation
        from app.ai.schemas.market_narrator import guardrail

        bad_output = {**_MN_OUTPUT_VALID, "warnings": ["保证收益不会损失"]}
        with pytest.raises(AiGuardrailViolation, match="保证收益"):
            guardrail({}, bad_output)

    def test_C7_guardrail_hits_ignore_stop_zh(self):
        from app.ai.errors import AiGuardrailViolation
        from app.ai.schemas.market_narrator import guardrail

        bad_output = {**_MN_OUTPUT_VALID, "avoid": ["忽略止损操作"]}
        with pytest.raises(AiGuardrailViolation, match="忽略止损"):
            guardrail({}, bad_output)

    def test_C8_guardrail_hits_ignore_stop_en(self):
        from app.ai.errors import AiGuardrailViolation
        from app.ai.schemas.market_narrator import guardrail

        bad_output = {**_MN_OUTPUT_VALID, "preferredSetups": ["ignore stop losses"]}
        with pytest.raises(AiGuardrailViolation, match="ignore stop"):
            guardrail({}, bad_output)

    def test_C9_clean_output_passes(self):
        from app.ai.schemas.market_narrator import guardrail

        guardrail({}, _MN_OUTPUT_VALID)  # must not raise

    def test_C10_se_guardrail_hits_buy_now(self):
        from app.ai.errors import AiGuardrailViolation
        from app.ai.schemas.setup_explainer import guardrail

        bad_output = {**_SE_OUTPUT_VALID, "label": "Just buy now signal"}
        with pytest.raises(AiGuardrailViolation, match="buy now"):
            guardrail({}, bad_output)

    def test_C11_se_guardrail_clean_passes(self):
        from app.ai.schemas.setup_explainer import guardrail

        guardrail({}, _SE_OUTPUT_VALID)  # must not raise

    def test_C12_banned_phrases_identical_across_modules(self):
        from app.ai.schemas.market_narrator import BANNED_PHRASES as mn_phrases
        from app.ai.schemas.setup_explainer import BANNED_PHRASES as se_phrases

        assert mn_phrases == se_phrases, "BANNED_PHRASES must be identical across schema modules"
        assert len(mn_phrases) == 6


# ---------------------------------------------------------------------------
# §D — Endpoint end-to-end (mock LiteLLM + TestClient)
# ---------------------------------------------------------------------------


def _make_litellm_mock(output: dict, cost: Decimal = Decimal("0.001234")):
    """Return a _call_litellm replacement that returns fixed data."""

    def mock(route, input_dict, output_schema, system_prompt=""):
        return output, 10, 5, cost

    return mock


class TestEndpointIntegration:
    def test_D1_market_narrator_success(self, client, monkeypatch):
        """POST /api/ai/market_narrator → 200, valid envelope, costUsd > 0 (D072)."""
        import app.ai.gateway as gw

        monkeypatch.setattr(gw, "_call_litellm", _make_litellm_mock(_MN_OUTPUT_VALID))
        resp = client.post("/api/ai/market_narrator", json={"input": _MN_INPUT_VALID})

        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "success"

        d = body["data"]
        assert isinstance(d["memoId"], int) and d["memoId"] > 0
        assert d["taskType"] == "market_narrator"
        assert d["schemaVersion"] == "v1"
        assert d["output"] == _MN_OUTPUT_VALID

        m = d["meta"]
        assert float(m["costUsd"]) > 0
        assert m["tokensIn"] == 10
        assert m["tokensOut"] == 5
        assert m["cacheHit"] is False
        assert m["tier"] == "default"
        assert "modelUsed" in m
        assert "latencyMs" in m

    def test_D2_setup_explainer_success(self, client, monkeypatch):
        """POST /api/ai/setup_explainer → 200, valid envelope."""
        import app.ai.gateway as gw

        monkeypatch.setattr(gw, "_call_litellm", _make_litellm_mock(_SE_OUTPUT_VALID))
        resp = client.post("/api/ai/setup_explainer", json={"input": _SE_INPUT_VALID})

        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "success"
        d = body["data"]
        assert d["taskType"] == "setup_explainer"
        assert d["schemaVersion"] == "v1"
        assert d["output"] == _SE_OUTPUT_VALID
        assert float(d["meta"]["costUsd"]) > 0

    def test_D3_guardrail_violation_returns_409(self, client, monkeypatch):
        """mock returns 'buy now' in headline → guardrail catches → 409 AI_GUARDRAIL_VIOLATION."""
        import app.ai.gateway as gw

        bad_output = {**_MN_OUTPUT_VALID, "headline": "Just buy now the dip"}
        monkeypatch.setattr(gw, "_call_litellm", _make_litellm_mock(bad_output))

        resp = client.post("/api/ai/market_narrator", json={"input": _MN_INPUT_VALID})
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "AI_GUARDRAIL_VIOLATION"

    def test_D4_missing_required_field_returns_422(self, client):
        """Input missing marketScore → 422 VALIDATION_ERROR."""
        bad_input = {k: v for k, v in _MN_INPUT_VALID.items() if k != "marketScore"}
        resp = client.post("/api/ai/market_narrator", json={"input": bad_input})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_D5_mn_cost_usd_written_to_db(self, client, db_session, monkeypatch):
        """D072 verification: ai_memos row has cost_usd > 0 after market_narrator call."""
        import app.ai.gateway as gw
        from app.models.ai_memo import AiMemo

        monkeypatch.setattr(gw, "_call_litellm", _make_litellm_mock(_MN_OUTPUT_VALID))
        resp = client.post("/api/ai/market_narrator", json={"input": _MN_INPUT_VALID})

        assert resp.status_code == 200
        memo_id = resp.json()["data"]["memoId"]

        # Expire any cached state and re-query
        db_session.expire_all()
        memo = db_session.query(AiMemo).filter(AiMemo.id == memo_id).first()
        assert memo is not None
        assert memo.cost_usd > 0

    def test_D6_guardrail_violation_no_new_memo(self, client, db_session, monkeypatch):
        """409 guardrail path: ai_memos count does not increase."""
        import app.ai.gateway as gw
        from app.models.ai_memo import AiMemo

        bad_output = {**_MN_OUTPUT_VALID, "summary": "go sell now immediately"}
        monkeypatch.setattr(gw, "_call_litellm", _make_litellm_mock(bad_output))

        count_before = db_session.query(AiMemo).count()
        resp = client.post("/api/ai/market_narrator", json={"input": _MN_INPUT_VALID})
        assert resp.status_code == 409

        db_session.expire_all()
        assert db_session.query(AiMemo).count() == count_before


# ---------------------------------------------------------------------------
# §E — Live smoke (@pytest.mark.live, skipped when OPENAI_API_KEY absent)
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_E1_market_narrator_live_smoke(db_session):
    """Real LiteLLM/OpenAI call — validates D072 cost fix is live on market_narrator.

    Requires OPENAI_API_KEY env var; automatically skipped when absent.
    Run manually: pytest backend/tests/test_ai_schemas_f209.py -m live -v
    """
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set — skipping live smoke")

    from app.ai.gateway import AiGateway
    from app.ai.schemas.market_narrator import MarketNarratorOutput
    from app.models.ai_memo import AiMemo

    result = AiGateway(db_session).run(
        task_type="market_narrator",
        input_dict=_MN_INPUT_VALID,
        no_cache=True,
    )

    # D072 verification: cost must be > 0 from real provider
    assert result.meta.cost_usd > 0, "D072: cost_usd must be > 0 from real call"

    # Output must parse against the schema
    MarketNarratorOutput(**result.output)

    # Verify ai_memos row
    memo = db_session.query(AiMemo).filter(AiMemo.id == result.memo_id).first()
    assert memo is not None
    assert memo.cost_usd > 0, "D072: ai_memos.cost_usd must be > 0"
    assert memo.task_type == "market_narrator"
    assert memo.schema_version == "v1"
