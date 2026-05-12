"""F213-a: AI schema unit + integration tests — translate_article.

§TI — TranslateArticleInput constraints (TI1-TI6)
§TO — TranslateArticleOutput constraints (TO1-TO4)
§R  — REGISTRY completeness (R1-R3)
§G  — guardrail absence / no-op (G1)
§TT — routing tier resolution (TT1-TT4)
§INT — AiGateway integration via mocked LiteLLM (INT1-INT2)
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.ai.schemas.translate_article import (
    TranslateArticleInput,
    TranslateArticleOutput,
    SCHEMA_VERSION,
    SYSTEM_PROMPT,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_VALID_INPUT = {
    "title": "Microsoft (NASDAQ: MSFT) Reports Record Q2 Earnings",
    "contentText": (
        "Microsoft Corp reported record quarterly earnings, beating analyst "
        "estimates by $0.15 per share. Revenue rose 17% YoY to $62.0B. "
        "CEO Satya Nadella cited strong Azure cloud growth."
    ),
    "targetLang": "zh-CN",
}

_VALID_OUTPUT = {
    "titleZh": "Microsoft (NASDAQ: MSFT) 报告创纪录第二季度业绩",
    "contentZh": (
        "Microsoft Corp 公布创纪录的季度业绩，超出分析师每股预期 $0.15。"
        "收入同比增长 17% 至 620 亿美元。首席执行官 Satya Nadella 表示 Azure 云业务增长强劲。"
    ),
}


# ---------------------------------------------------------------------------
# §TI — TranslateArticleInput
# ---------------------------------------------------------------------------


class TestTranslateArticleInput:
    def test_TI1_empty_title_rejected(self):
        """title='' → ValidationError (min_length=1)."""
        data = {**_VALID_INPUT, "title": ""}
        with pytest.raises(ValidationError):
            TranslateArticleInput(**data)

    def test_TI2_title_length_501_rejected(self):
        """title length=501 → ValidationError (max_length=500)."""
        data = {**_VALID_INPUT, "title": "A" * 501}
        with pytest.raises(ValidationError):
            TranslateArticleInput(**data)

    def test_TI3_contentText_length_20001_rejected(self):
        """contentText length=20001 → ValidationError (max_length=20000)."""
        data = {**_VALID_INPUT, "contentText": "x" * 20001}
        with pytest.raises(ValidationError):
            TranslateArticleInput(**data)

    def test_TI4_extra_field_rejected(self):
        """extra=forbid: unknown field sourceUrl → ValidationError."""
        data = {**_VALID_INPUT, "sourceUrl": "https://example.com"}
        with pytest.raises(ValidationError):
            TranslateArticleInput(**data)

    def test_TI5_targetLang_non_zh_rejected(self):
        """targetLang='en-US' → ValidationError (Literal mismatch)."""
        data = {**_VALID_INPUT, "targetLang": "en-US"}
        with pytest.raises(ValidationError):
            TranslateArticleInput(**data)

    def test_TI6_valid_input_with_emoji_and_ticker(self):
        """Input with emoji + NASDAQ:MSFT mixed → passes."""
        data = {
            "title": "NVDA 🚀 Surges 10% — What's Next for NASDAQ: NVDA?",
            "contentText": "NVIDIA Corp (NASDAQ: NVDA) jumped $88 (+10.2%) on strong AI chip demand.",
            "targetLang": "zh-CN",
        }
        obj = TranslateArticleInput(**data)
        assert obj.targetLang == "zh-CN"
        assert "NVDA" in obj.title

    def test_TI_targetLang_default_is_zh_CN(self):
        """targetLang omitted → defaults to 'zh-CN'."""
        data = {"title": "Test Headline", "contentText": "Test content body."}
        obj = TranslateArticleInput(**data)
        assert obj.targetLang == "zh-CN"

    def test_TI_empty_contentText_rejected(self):
        """contentText='' → ValidationError (min_length=1)."""
        data = {**_VALID_INPUT, "contentText": ""}
        with pytest.raises(ValidationError):
            TranslateArticleInput(**data)

    def test_TI_title_max_boundary_accepted(self):
        """title length=500 (boundary) → passes."""
        data = {**_VALID_INPUT, "title": "A" * 500}
        obj = TranslateArticleInput(**data)
        assert len(obj.title) == 500

    def test_TI_contentText_max_boundary_accepted(self):
        """contentText length=20000 (boundary) → passes."""
        data = {**_VALID_INPUT, "contentText": "x" * 20000}
        obj = TranslateArticleInput(**data)
        assert len(obj.contentText) == 20000


# ---------------------------------------------------------------------------
# §TO — TranslateArticleOutput
# ---------------------------------------------------------------------------


class TestTranslateArticleOutput:
    def test_TO1_empty_titleZh_rejected(self):
        """titleZh='' → ValidationError (min_length=1)."""
        data = {**_VALID_OUTPUT, "titleZh": ""}
        with pytest.raises(ValidationError):
            TranslateArticleOutput(**data)

    def test_TO2_contentZh_length_25001_rejected(self):
        """contentZh length=25001 → ValidationError (max_length=25000)."""
        data = {**_VALID_OUTPUT, "contentZh": "字" * 25001}
        with pytest.raises(ValidationError):
            TranslateArticleOutput(**data)

    def test_TO3_extra_field_rejected(self):
        """extra=forbid: unknown field → ValidationError."""
        data = {**_VALID_OUTPUT, "confidence": 0.95}
        with pytest.raises(ValidationError):
            TranslateArticleOutput(**data)

    def test_TO4_valid_chinese_sample_with_ascii_ticker(self):
        """Chinese text mixed with ASCII company code → passes."""
        obj = TranslateArticleOutput(**_VALID_OUTPUT)
        assert "Microsoft" in obj.titleZh  # company name preserved
        assert "NASDAQ: MSFT" in obj.titleZh
        assert obj.contentZh.startswith("Microsoft Corp")

    def test_TO_empty_contentZh_rejected(self):
        """contentZh='' → ValidationError (min_length=1)."""
        data = {**_VALID_OUTPUT, "contentZh": ""}
        with pytest.raises(ValidationError):
            TranslateArticleOutput(**data)

    def test_TO_titleZh_max_boundary_accepted(self):
        """titleZh length=500 → passes."""
        data = {**_VALID_OUTPUT, "titleZh": "标" * 500}
        obj = TranslateArticleOutput(**data)
        assert len(obj.titleZh) == 500

    def test_TO_contentZh_max_boundary_accepted(self):
        """contentZh length=25000 → passes."""
        data = {**_VALID_OUTPUT, "contentZh": "字" * 25000}
        obj = TranslateArticleOutput(**data)
        assert len(obj.contentZh) == 25000


# ---------------------------------------------------------------------------
# §R — REGISTRY completeness
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_R1_translate_article_in_registry(self):
        """REGISTRY['translate_article'] exists."""
        from app.ai.schemas import REGISTRY

        assert "translate_article" in REGISTRY

    def test_R2_input_output_schema_types_correct(self):
        """REGISTRY['translate_article'].input_schema / output_schema types correct."""
        from app.ai.schemas import REGISTRY, SchemaPair

        pair = REGISTRY["translate_article"]
        assert isinstance(pair, SchemaPair)
        assert pair.input_schema is TranslateArticleInput
        assert pair.output_schema is TranslateArticleOutput

    def test_R3_system_prompt_nonempty_and_contains_finance_keyword(self):
        """SYSTEM_PROMPT is non-empty and contains '金融' keyword."""
        from app.ai.schemas import REGISTRY

        prompt = REGISTRY["translate_article"].system_prompt
        assert prompt, "system_prompt must not be empty"
        assert "金融" in prompt


# ---------------------------------------------------------------------------
# §G — guardrail absence / no-op
# ---------------------------------------------------------------------------


class TestGuardrailAbsence:
    def test_G1_guardrail_run_translate_article_noop(self):
        """guardrail.run('translate_article', ...) is a no-op (not registered)."""
        from app.ai import guardrail as gr

        # Must not raise regardless of output content
        gr.run("translate_article", _VALID_INPUT, _VALID_OUTPUT)

    def test_G1b_translate_article_not_in_hooks(self):
        """translate_article is NOT registered in guardrail._HOOKS (by design)."""
        from app.ai import guardrail as gr

        assert "translate_article" not in gr._HOOKS


# ---------------------------------------------------------------------------
# §TT — routing tier resolution
# ---------------------------------------------------------------------------


class TestRoutingTier:
    def test_TT1_resolve_tier_returns_default(self):
        """resolve_tier('translate_article') == 'default'."""
        from app.ai.routing import resolve_tier

        assert resolve_tier("translate_article") == "default"

    def test_TT2_known_task_types_length_9_contains_translate_article(self):
        """known_task_types() has 9 entries (8 contract tasks + echo) including translate_article."""
        from app.ai.routing import known_task_types

        types = known_task_types()
        assert "translate_article" in types
        assert len(types) == 9

    def test_TT3_resolve_without_override_uses_default_model(self, monkeypatch):
        """resolve('translate_article') with no override → tier=default, model=settings.ai_model_default."""
        import app.ai.routing as routing
        from app.config import settings

        monkeypatch.setattr(routing, "_parse_overrides", lambda: {})
        route = routing.resolve("translate_article")
        assert route.tier == "default"
        assert route.model == settings.ai_model_default
        assert route.base_url is None

    def test_TT4_resolve_with_deepseek_override_returns_deepseek_config(self, monkeypatch):
        """resolve('translate_article') with monkeypatched DeepSeek override → returns override config."""
        import app.ai.routing as routing

        fake_override = {
            "translate_article": {
                "model": "openai/deepseek-v4-flash",
                "base_url": "https://api.deepseek.com",
                "api_key": "sk-testkey",
                "input_cost_per_1m": 0.14,
                "output_cost_per_1m": 0.28,
            }
        }
        monkeypatch.setattr(routing, "_parse_overrides", lambda: fake_override)
        route = routing.resolve("translate_article")
        assert route.model == "openai/deepseek-v4-flash"
        assert route.base_url == "https://api.deepseek.com"
        assert route.api_key == "sk-testkey"
        assert route.custom_input_cost == pytest.approx(0.14)
        assert route.custom_output_cost == pytest.approx(0.28)


# ---------------------------------------------------------------------------
# §INT — AiGateway integration (mocked LiteLLM)
# ---------------------------------------------------------------------------


def _make_litellm_mock(output: dict, cost: Decimal = Decimal("0.000028")):
    """Return a _call_litellm replacement returning fixed data."""

    def mock(route, input_dict, output_schema, system_prompt=""):
        return output, 120, 80, cost

    return mock


class TestIntegration:
    def test_INT1_translate_article_full_pipeline(self, client, monkeypatch):
        """POST /api/ai/translate_article → 200, valid schema output, memo written."""
        import app.ai.gateway as gw

        monkeypatch.setattr(gw, "_call_litellm", _make_litellm_mock(_VALID_OUTPUT))
        resp = client.post(
            "/api/ai/translate_article",
            json={"input": _VALID_INPUT, "noCache": True},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "success"
        d = body["data"]
        assert d["taskType"] == "translate_article"
        assert d["schemaVersion"] == SCHEMA_VERSION
        assert d["output"]["titleZh"] == _VALID_OUTPUT["titleZh"]
        assert d["output"]["contentZh"] == _VALID_OUTPUT["contentZh"]
        m = d["meta"]
        assert m["cacheHit"] is False
        assert m["tier"] == "default"
        assert m["tokensIn"] == 120
        assert m["tokensOut"] == 80
        assert float(m["costUsd"]) > 0

    def test_INT2_cache_hit_on_second_call(self, client, monkeypatch):
        """Same input twice → second call returns cacheHit=true."""
        import app.ai.gateway as gw

        mock = _make_litellm_mock(_VALID_OUTPUT)
        monkeypatch.setattr(gw, "_call_litellm", mock)

        # First call — real LLM
        resp1 = client.post(
            "/api/ai/translate_article",
            json={"input": _VALID_INPUT},
        )
        assert resp1.status_code == 200
        assert resp1.json()["data"]["meta"]["cacheHit"] is False

        # Second call with same input — should hit cache
        resp2 = client.post(
            "/api/ai/translate_article",
            json={"input": _VALID_INPUT},
        )
        assert resp2.status_code == 200
        assert resp2.json()["data"]["meta"]["cacheHit"] is True
