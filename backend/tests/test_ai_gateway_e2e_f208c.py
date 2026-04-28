"""F208-c: end-to-end tests for AiGateway + POST /api/ai/{task_type} endpoint.

§A — gateway 7 paths (mock LiteLLM)
§B — endpoint envelope alias + 6 error-code mappings (FastAPI TestClient)
§C — live smoke (real OpenAI, @pytest.mark.live, skipped when key absent)
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal

import pytest

from app.ai.errors import (
    AiBudgetExceeded,
    AiGuardrailViolation,
    AiProviderError,
    AiSchemaError,
)
from app.ai.gateway import AiGateway
from app.models.ai_memo import AiMemo

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_ECHO_INPUT = {"text": "ping"}
_ECHO_OUTPUT = {"echoed": "pong"}


def _make_litellm_mock(output: dict | None = None, raise_exc: Exception | None = None):
    """Return a _call_litellm replacement that either returns fixed data or raises."""
    result = output or _ECHO_OUTPUT

    def mock(model, input_dict, output_schema, api_key):
        if raise_exc is not None:
            raise raise_exc
        return result, 10, 5, Decimal("0.001")

    return mock


# ---------------------------------------------------------------------------
# §A — Gateway 7 paths (all via AiGateway(db).run("echo", ...) direct call)
# ---------------------------------------------------------------------------


class TestGatewayPaths:
    def test_A1_success_path(self, db_session, monkeypatch):
        """Cache miss → LiteLLM called → memo written → GatewayResult returned."""
        monkeypatch.setattr("app.ai.gateway._call_litellm", _make_litellm_mock())

        result = AiGateway(db_session).run(task_type="echo", input_dict=_ECHO_INPUT)

        assert result.meta.cache_hit is False
        assert isinstance(result.memo_id, int) and result.memo_id > 0
        assert result.output == _ECHO_OUTPUT
        assert result.meta.tokens_in == 10
        assert result.meta.tokens_out == 5
        assert result.meta.cost_usd == Decimal("0.001")
        assert result.task_type == "echo"
        assert result.schema_version == "v1"

        count = db_session.query(AiMemo).count()
        assert count == 1

    def test_A2_cache_hit(self, db_session, monkeypatch):
        """Second identical call → cache_hit=True, LiteLLM called once, no new memo row."""
        call_count = [0]

        def mock(model, input_dict, output_schema, api_key):
            call_count[0] += 1
            return _ECHO_OUTPUT, 10, 5, Decimal("0.001")

        monkeypatch.setattr("app.ai.gateway._call_litellm", mock)

        result1 = AiGateway(db_session).run(task_type="echo", input_dict=_ECHO_INPUT)
        result2 = AiGateway(db_session).run(task_type="echo", input_dict=_ECHO_INPUT)

        assert result1.meta.cache_hit is False
        assert result2.meta.cache_hit is True
        assert result2.meta.tokens_in == 0
        assert result2.meta.tokens_out == 0
        assert result2.meta.cost_usd == Decimal("0")
        assert result2.meta.model_used == "cache"
        assert result2.memo_id == result1.memo_id  # same cached memo
        assert call_count[0] == 1  # LiteLLM hit only once

        assert db_session.query(AiMemo).count() == 1

    def test_A3_no_cache_bypasses_cache(self, db_session, monkeypatch):
        """no_cache=True on second call → fresh LiteLLM call, second memo row inserted."""
        call_count = [0]

        def mock(model, input_dict, output_schema, api_key):
            call_count[0] += 1
            return _ECHO_OUTPUT, 10, 5, Decimal("0.001")

        monkeypatch.setattr("app.ai.gateway._call_litellm", mock)

        result1 = AiGateway(db_session).run(task_type="echo", input_dict=_ECHO_INPUT)
        result2 = AiGateway(db_session).run(
            task_type="echo", input_dict=_ECHO_INPUT, no_cache=True
        )

        assert result1.meta.cache_hit is False
        assert result2.meta.cache_hit is False
        assert call_count[0] == 2
        assert db_session.query(AiMemo).count() == 2

    def test_A4_budget_exceeded_no_litellm_no_memo(self, db_session, monkeypatch):
        """Month-to-date cost ≥ cap → AiBudgetExceeded, LiteLLM not called, no memo."""
        from datetime import datetime, timedelta, timezone

        month_start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        db_session.add(
            AiMemo(
                task_type="echo",
                input_hash="budget_test",
                input_json="{}",
                output_json="{}",
                schema_version="v1",
                model_used="gpt-5.4-nano",
                tier="default",
                tokens_in=1000,
                tokens_out=500,
                cost_usd=Decimal("20.0"),
                latency_ms=1000,
                created_at=month_start + timedelta(hours=1),
            )
        )
        db_session.commit()

        litellm_called = []
        monkeypatch.setattr(
            "app.ai.gateway._call_litellm",
            lambda model, input_dict, output_schema, api_key: litellm_called.append(1)
            or (_ECHO_OUTPUT, 0, 0, Decimal("0")),
        )
        from app.config import settings
        monkeypatch.setattr(settings, "ai_monthly_budget_usd", 20.0)

        with pytest.raises(AiBudgetExceeded):
            AiGateway(db_session).run(task_type="echo", input_dict=_ECHO_INPUT)

        assert not litellm_called, "LiteLLM must not be called when budget exceeded"
        assert db_session.query(AiMemo).count() == 1  # only the pre-inserted row

    def test_A5_provider_error_no_memo(self, db_session, monkeypatch):
        """LiteLLM raises AiProviderError → propagated, no memo written."""
        monkeypatch.setattr(
            "app.ai.gateway._call_litellm",
            _make_litellm_mock(raise_exc=AiProviderError("timeout")),
        )

        with pytest.raises(AiProviderError):
            AiGateway(db_session).run(task_type="echo", input_dict=_ECHO_INPUT)

        assert db_session.query(AiMemo).count() == 0

    def test_A6_schema_error_on_bad_output_no_memo(self, db_session, monkeypatch):
        """LiteLLM returns wrong output shape → AiSchemaError, no memo written."""
        monkeypatch.setattr(
            "app.ai.gateway._call_litellm",
            _make_litellm_mock(output={"wrong_field": "bad"}),
        )

        with pytest.raises(AiSchemaError):
            AiGateway(db_session).run(task_type="echo", input_dict=_ECHO_INPUT)

        assert db_session.query(AiMemo).count() == 0

    def test_A7_guardrail_violation_no_memo(self, db_session, monkeypatch):
        """Guardrail hook raises AiGuardrailViolation → propagated, no memo written."""
        from app.ai import guardrail

        monkeypatch.setattr("app.ai.gateway._call_litellm", _make_litellm_mock())

        def bad_hook(input_dict, output_dict):
            raise AiGuardrailViolation("rejected by guardrail")

        guardrail.register("echo", bad_hook)
        try:
            with pytest.raises(AiGuardrailViolation, match="rejected"):
                AiGateway(db_session).run(task_type="echo", input_dict=_ECHO_INPUT)

            assert db_session.query(AiMemo).count() == 0
        finally:
            guardrail._HOOKS.pop("echo", None)


# ---------------------------------------------------------------------------
# §A — Extra unit tests (standards #12 and #13)
# ---------------------------------------------------------------------------


def test_guardrail_default_noop():
    """guardrail.run with no registered hook is a no-op (standard #12)."""
    from app.ai import guardrail

    guardrail._HOOKS.pop("echo", None)
    guardrail.run("echo", {"text": "x"}, {"echoed": "x"})  # must not raise


def test_guardrail_register_then_run():
    """After register(), hook is invoked by run() (standard #12)."""
    from app.ai import guardrail

    called = []

    def hook(inp, out):
        called.append((inp, out))

    guardrail.register("__test_unit__", hook)
    try:
        guardrail.run("__test_unit__", {"k": "v"}, {"r": "s"})
        assert called == [({"k": "v"}, {"r": "s"})]
    finally:
        guardrail._HOOKS.pop("__test_unit__", None)


def test_gateway_no_toplevel_litellm_import():
    """Importing gateway must not trigger litellm load (standard #13 lazy import).

    Carefully isolated: removes litellm from sys.modules, reloads gateway in-place
    (using importlib.reload so the existing module object is reused — must not
    create a *new* module instance, since other modules like app.routers.ai hold
    cached references to the original module object).
    """
    import importlib

    saved_litellm = {
        k: sys.modules.pop(k)
        for k in list(sys.modules)
        if k == "litellm" or k.startswith("litellm.")
    }
    try:
        import app.ai.gateway  # noqa: PLC0415
        importlib.reload(app.ai.gateway)
        assert "litellm" not in sys.modules, "gateway top-level must not import litellm"
    finally:
        sys.modules.update(saved_litellm)


# ---------------------------------------------------------------------------
# §B fixtures — shared across endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
def market_narrator_schema():
    """Temporarily register a minimal market_narrator schema (§B endpoint tests)."""
    from pydantic import BaseModel

    from app.ai.schemas import REGISTRY, SchemaPair

    class _MNInput(BaseModel):
        symbol: str
        model_config = {"extra": "forbid"}

    class _MNOutput(BaseModel):
        summary: str
        model_config = {"extra": "forbid"}

    pair = SchemaPair(_MNInput, _MNOutput)
    # Save original (F209-a registers the real schema on module load)
    original = REGISTRY.get("market_narrator")
    REGISTRY["market_narrator"] = pair
    try:
        yield pair
    finally:
        if original is not None:
            REGISTRY["market_narrator"] = original
        else:
            REGISTRY.pop("market_narrator", None)


# ---------------------------------------------------------------------------
# §B — Endpoint envelope alias + 6 error-code mappings
# ---------------------------------------------------------------------------


class TestEndpointEnvelope:
    def test_B_echo_task_literal_422(self, client):
        """POST /api/ai/echo → 422 VALIDATION_ERROR (not in 7-value Literal)."""
        resp = client.post("/api/ai/echo", json={"input": {"text": "test"}})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_B_success_camelcase_envelope(self, client, market_narrator_schema, monkeypatch):
        """Success path → strict camelCase envelope matches API-CONTRACT."""
        import app.ai.gateway as gw

        def fake_litellm(model, input_dict, output_schema, api_key):
            return {"summary": "bullish"}, 10, 5, Decimal("0.001")

        monkeypatch.setattr(gw, "_call_litellm", fake_litellm)
        resp = client.post("/api/ai/market_narrator", json={"input": {"symbol": "AAPL"}})
        assert resp.status_code == 200

        body = resp.json()
        assert body["message"] == "success"
        d = body["data"]
        assert "memoId" in d and isinstance(d["memoId"], int)
        assert d["taskType"] == "market_narrator"
        assert "schemaVersion" in d
        assert d["output"] == {"summary": "bullish"}

        m = d["meta"]
        assert "modelUsed" in m
        assert m["tokensIn"] == 10
        assert m["tokensOut"] == 5
        assert "costUsd" in m
        assert "latencyMs" in m
        assert m["cacheHit"] is False
        assert "tier" in m

        # Verify snake_case aliases are absent at top level
        assert "memo_id" not in d
        assert "cache_hit" not in m

    def test_B_error_unknown_task_literal_422(self, client):
        """task_type not in 7 Literal values → 422 VALIDATION_ERROR."""
        resp = client.post("/api/ai/unknown_task", json={"input": {}})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_B_error_registry_key_error_422(self, client):
        """task_type in Literal but not in REGISTRY → 422 VALIDATION_ERROR."""
        # market_narrator is a valid Literal but not registered (no fixture here)
        resp = client.post("/api/ai/market_narrator", json={"input": {"symbol": "AAPL"}})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_B_error_input_validation_422(self, client, market_narrator_schema, monkeypatch):
        """Input fails Pydantic schema validation → 422 VALIDATION_ERROR."""
        resp = client.post(
            "/api/ai/market_narrator",
            json={"input": {"wrong_field": "bad"}},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_B_error_provider_error_502(self, client, market_narrator_schema, monkeypatch):
        """AiProviderError → 502 AI_PROVIDER_ERROR."""
        import app.ai.gateway as gw

        def fail(model, input_dict, output_schema, api_key):
            raise AiProviderError("timeout")

        monkeypatch.setattr(gw, "_call_litellm", fail)
        resp = client.post("/api/ai/market_narrator", json={"input": {"symbol": "AAPL"}})
        assert resp.status_code == 502
        assert resp.json()["error"]["code"] == "AI_PROVIDER_ERROR"

    def test_B_error_schema_error_502(self, client, market_narrator_schema, monkeypatch):
        """Output fails secondary schema validation → 502 AI_SCHEMA_ERROR."""
        import app.ai.gateway as gw

        def bad_output(model, input_dict, output_schema, api_key):
            return {"wrong_field": "bad"}, 10, 5, Decimal("0.001")

        monkeypatch.setattr(gw, "_call_litellm", bad_output)
        resp = client.post("/api/ai/market_narrator", json={"input": {"symbol": "AAPL"}})
        assert resp.status_code == 502
        assert resp.json()["error"]["code"] == "AI_SCHEMA_ERROR"

    def test_B_error_budget_exceeded_429(self, client, market_narrator_schema, monkeypatch):
        """AiBudgetExceeded → 429 AI_BUDGET_EXCEEDED."""
        import app.ai.gateway as gw

        def mock_budget(db, *, cap_usd=None, now=None):
            raise AiBudgetExceeded("over cap")

        monkeypatch.setattr(gw, "assert_within_budget", mock_budget)
        resp = client.post("/api/ai/market_narrator", json={"input": {"symbol": "AAPL"}})
        assert resp.status_code == 429
        assert resp.json()["error"]["code"] == "AI_BUDGET_EXCEEDED"

    def test_B_error_guardrail_violation_409(self, client, market_narrator_schema, monkeypatch):
        """AiGuardrailViolation → 409 AI_GUARDRAIL_VIOLATION."""
        import app.ai.gateway as gw
        from app.ai import guardrail as gr

        def ok_litellm(model, input_dict, output_schema, api_key):
            return {"summary": "ok"}, 10, 5, Decimal("0.001")

        def bad_guardrail(task_type, input_dict, output_dict):
            raise AiGuardrailViolation("rejected")

        monkeypatch.setattr(gw, "_call_litellm", ok_litellm)
        monkeypatch.setattr(gr, "run", bad_guardrail)
        resp = client.post("/api/ai/market_narrator", json={"input": {"symbol": "AAPL"}})
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "AI_GUARDRAIL_VIOLATION"

    def test_B_openapi_visible_with_7_task_types(self, client):
        """POST /api/ai/{task_type} appears in /openapi.json (standard #11)."""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        openapi = resp.json()
        paths = openapi.get("paths", {})
        assert "/api/ai/{task_type}" in paths, "AI endpoint must appear in OpenAPI schema"


# ---------------------------------------------------------------------------
# §C — Live smoke (real OpenAI; skipped when OPENAI_API_KEY is absent)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# §F210-a — C9/C10 guardrail integration (trade_plan + candidate_ranker)
# ---------------------------------------------------------------------------

_TP_INPUT = {
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

_TP_OUTPUT_VALID = {
    "memo": "AAPL breaks out above the pivot on strong volume. Earnings risk is SAFE. Trail stop with 21EMA after 2R.",
    "management": ["Hold through initial volatility", "Move stop to BE near 2R"],
    "entry": 182.50,
    "stop": 178.00,
    "size": 55,
}

_CR_INPUT = {
    "regime": "CONSTRUCTIVE",
    "regimeScore": 72,
    "candidates": [
        {
            "ticker": "AAPL",
            "setupType": "BREAKOUT",
            "setupQuality": "A",
            "trendScore": 4,
            "rsPercentile": 85.0,
            "distanceToEntryPct": 1.5,
            "rewardRisk": 2.5,
            "earningsRisk": "SAFE",
            "readySignal": True,
        },
        {
            "ticker": "MSFT",
            "setupType": "PULLBACK",
            "setupQuality": "B",
            "trendScore": 3,
            "rsPercentile": 70.0,
            "distanceToEntryPct": 0.5,
            "rewardRisk": 2.0,
            "earningsRisk": "SAFE",
            "readySignal": False,
        },
        {
            "ticker": "NVDA",
            "setupType": "RECLAIM",
            "setupQuality": "A",
            "trendScore": 5,
            "rsPercentile": 95.0,
            "distanceToEntryPct": 2.0,
            "rewardRisk": 3.0,
            "earningsRisk": "SAFE",
            "readySignal": True,
        },
    ],
}

_CR_OUTPUT_VALID = {
    "topCandidates": [
        {"ticker": "AAPL", "rank": 1, "reason": "Strong RS breakout with ready signal.", "action": "enter"},
        {"ticker": "NVDA", "rank": 2, "reason": "Highest RS reclaim with ready signal.", "action": "watch"},
        {"ticker": "MSFT", "rank": 3, "reason": "Solid pullback to support.", "action": "wait"},
    ]
}


class TestF210aGuardrailIntegration:
    def test_C9_trade_plan_guardrail_violation_no_memo(self, db_session, monkeypatch):
        """trade_plan: LLM returns modified size → AiGuardrailViolation, memo not written."""
        tampered_output = {**_TP_OUTPUT_VALID, "size": 99}  # size mismatch

        def mock_litellm(model, input_dict, output_schema, api_key):
            return tampered_output, 15, 10, Decimal("0.002")

        monkeypatch.setattr("app.ai.gateway._call_litellm", mock_litellm)
        count_before = db_session.query(AiMemo).count()

        with pytest.raises(AiGuardrailViolation, match="size"):
            AiGateway(db_session).run(task_type="trade_plan", input_dict=_TP_INPUT)

        assert db_session.query(AiMemo).count() == count_before

    def test_C10_candidate_ranker_no_guardrail_memo_written(self, db_session, monkeypatch):
        """candidate_ranker: valid LLM output → memo written, no guardrail called."""
        def mock_litellm(model, input_dict, output_schema, api_key):
            return _CR_OUTPUT_VALID, 20, 15, Decimal("0.003")

        monkeypatch.setattr("app.ai.gateway._call_litellm", mock_litellm)
        count_before = db_session.query(AiMemo).count()

        result = AiGateway(db_session).run(
            task_type="candidate_ranker", input_dict=_CR_INPUT
        )

        assert db_session.query(AiMemo).count() == count_before + 1
        assert result.output == _CR_OUTPUT_VALID
        assert result.meta.cache_hit is False


# ---------------------------------------------------------------------------
@pytest.mark.live
def test_C_echo_live_smoke(db_session):
    """Real OpenAI call with echo task — verifies full path end-to-end."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set — skipping live smoke")

    result = AiGateway(db_session).run(
        task_type="echo",
        input_dict={"text": "ping"},
        no_cache=True,
    )

    assert isinstance(result.output.get("echoed"), str), "echoed must be a string"
    assert len(result.output["echoed"]) > 0, "echoed must be non-empty"
    assert result.meta.cache_hit is False
    assert result.meta.tokens_in > 0
    assert result.meta.tokens_out > 0
    assert result.meta.cost_usd > Decimal("0")
    assert isinstance(result.memo_id, int) and result.memo_id > 0

    # Verify the row is in ai_memos
    row = db_session.get(AiMemo, result.memo_id)
    assert row is not None
    assert row.model_used != "cache"
    assert row.cost_usd > Decimal("0")


# ---------------------------------------------------------------------------
# §F211-a1 — C13 gateway integration (contradiction_detector routing + guardrail)
# ---------------------------------------------------------------------------

_CD_INPUT = {
    "ticker": "AAPL",
    "setupType": "BREAKOUT",
    "setupQuality": "A",
    "trendScore": 4,
    "rsPercentile": 82.5,
    "entry": 180.00,
    "stop": 175.00,
    "target2r": 190.00,
    "rewardRisk": 2.0,
    "accountRiskPct": 1.0,
    "earningsRisk": "SAFE",
    "daysToEarnings": 45,
    "regime": "CONSTRUCTIVE",
    "regimeScore": 70,
    "readySignal": True,
}

_CD_OUTPUT_CLEAN = {
    "contradictions": [],
    "recommendation": "No major contradictions.",
}

_CD_OUTPUT_BANNED = {
    "contradictions": [],
    "recommendation": "You should buy now at entry.",
}


class TestF211a1GatewayIntegration:
    def test_C13a_contradiction_detector_success_memo_written(self, db_session, monkeypatch):
        """contradiction_detector: mock LLM clean output → memo written, guardrail passes."""
        def mock_litellm(model, input_dict, output_schema, api_key):
            return _CD_OUTPUT_CLEAN, 20, 10, Decimal("0.001")

        monkeypatch.setattr("app.ai.gateway._call_litellm", mock_litellm)
        count_before = db_session.query(AiMemo).count()

        result = AiGateway(db_session).run(
            task_type="contradiction_detector", input_dict=_CD_INPUT
        )

        assert db_session.query(AiMemo).count() == count_before + 1
        assert result.output == _CD_OUTPUT_CLEAN
        assert result.meta.cache_hit is False
        assert result.task_type == "contradiction_detector"

    def test_C13b_banned_phrase_in_recommendation_violation_no_memo(self, db_session, monkeypatch):
        """contradiction_detector: recommendation contains 'buy now' → AiGuardrailViolation, no new memo."""
        def mock_litellm(model, input_dict, output_schema, api_key):
            return _CD_OUTPUT_BANNED, 20, 10, Decimal("0.001")

        monkeypatch.setattr("app.ai.gateway._call_litellm", mock_litellm)
        count_before = db_session.query(AiMemo).count()

        with pytest.raises(AiGuardrailViolation, match="banned phrase"):
            AiGateway(db_session).run(
                task_type="contradiction_detector", input_dict=_CD_INPUT
            )

        assert db_session.query(AiMemo).count() == count_before
