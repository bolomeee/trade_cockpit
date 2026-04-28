"""F211-a1: AI schema unit tests — contradiction_detector + news_summarizer + journal_assistant.

§CI — ContradictionDetectorInput constraints (CI1-CI6)
§CO — ContradictionDetectorOutput constraints (CO1-CO6)
§CG — contradiction_detector guardrail (CG1-CG3)
§NI — NewsSummarizerInput constraints (NI1-NI6)
§NO — NewsSummarizerOutput constraints (NO1-NO4)
§NG — news_summarizer guardrail (NG1-NG2)
§JI — JournalAssistantInput constraints (JI1-JI6)
§JO — JournalAssistantOutput constraints (JO1-JO3)
§JG — journal_assistant guardrail (JG1-JG2)
§R  — REGISTRY + routing tier (R1-R7)
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.ai.errors import AiGuardrailViolation
from app.ai.schemas.contradiction_detector import (
    ContradictionDetectorInput,
    ContradictionDetectorOutput,
    Contradiction,
    guardrail as cd_guardrail,
)

# ---------------------------------------------------------------------------
# Shared fixtures — contradiction_detector
# ---------------------------------------------------------------------------

_CD_INPUT_VALID = {
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

_CONTRADICTION_ITEM = {
    "type": "earnings_risk",
    "severity": "MEDIUM",
    "text": "Earnings in 12 days — holds through report.",
}

_CD_OUTPUT_VALID = {
    "contradictions": [_CONTRADICTION_ITEM],
    "recommendation": "Reduce position size by 50% due to earnings proximity.",
}

_CD_OUTPUT_EMPTY = {
    "contradictions": [],
    "recommendation": "No major contradictions.",
}


# ---------------------------------------------------------------------------
# §CI — ContradictionDetectorInput
# ---------------------------------------------------------------------------


class TestContradictionInput:
    def test_CI1_full_valid_input(self):
        """All 15 fields within constraints → passes."""
        obj = ContradictionDetectorInput(**_CD_INPUT_VALID)
        assert obj.ticker == "AAPL"
        assert obj.readySignal is True

    def test_CI2_earnings_risk_and_days_none_accepted(self):
        """earningsRisk=None + daysToEarnings=None → passes (F210-c earningsRisk-null lesson)."""
        data = {**_CD_INPUT_VALID, "earningsRisk": None, "daysToEarnings": None}
        obj = ContradictionDetectorInput(**data)
        assert obj.earningsRisk is None
        assert obj.daysToEarnings is None

    def test_CI3_trend_score_6_rejected(self):
        """trendScore=6 → ValidationError (le=5)."""
        data = {**_CD_INPUT_VALID, "trendScore": 6}
        with pytest.raises(ValidationError):
            ContradictionDetectorInput(**data)

    def test_CI4_rs_percentile_101_rejected(self):
        """rsPercentile=101 → ValidationError (le=100)."""
        data = {**_CD_INPUT_VALID, "rsPercentile": 101.0}
        with pytest.raises(ValidationError):
            ContradictionDetectorInput(**data)

    def test_CI5_invalid_regime_rejected(self):
        """regime='BULLISH' (non-enum) → ValidationError."""
        data = {**_CD_INPUT_VALID, "regime": "BULLISH"}
        with pytest.raises(ValidationError):
            ContradictionDetectorInput(**data)

    def test_CI6_extra_field_rejected(self):
        """extra=forbid: unknown field → ValidationError."""
        data = {**_CD_INPUT_VALID, "volumeContext": 1.5}
        with pytest.raises(ValidationError):
            ContradictionDetectorInput(**data)


# ---------------------------------------------------------------------------
# §CO — ContradictionDetectorOutput
# ---------------------------------------------------------------------------


class TestContradictionOutput:
    def test_CO1_empty_contradictions_accepted(self):
        """contradictions=[] (min_length=0) + recommendation → passes."""
        obj = ContradictionDetectorOutput(**_CD_OUTPUT_EMPTY)
        assert obj.contradictions == []
        assert obj.recommendation == "No major contradictions."

    def test_CO2_five_contradictions_max_boundary(self):
        """5 contradictions (max_length=5) → passes."""
        items = [
            {"type": "earnings_risk", "severity": "HIGH", "text": f"Issue {i}."}
            for i in range(5)
        ]
        obj = ContradictionDetectorOutput(contradictions=items, recommendation="Review setup.")
        assert len(obj.contradictions) == 5

    def test_CO3_six_contradictions_rejected(self):
        """6 contradictions → ValidationError (max_length=5)."""
        items = [
            {"type": "other", "severity": "LOW", "text": f"Minor issue {i}."}
            for i in range(6)
        ]
        with pytest.raises(ValidationError):
            ContradictionDetectorOutput(contradictions=items, recommendation="Review.")

    def test_CO4_invalid_severity_rejected(self):
        """severity='CRITICAL' (non-enum) → ValidationError."""
        bad_item = {**_CONTRADICTION_ITEM, "severity": "CRITICAL"}
        with pytest.raises(ValidationError):
            ContradictionDetectorOutput(
                contradictions=[bad_item], recommendation="Review."
            )

    def test_CO5_recommendation_missing_rejected(self):
        """recommendation field absent → ValidationError."""
        with pytest.raises(ValidationError):
            ContradictionDetectorOutput(contradictions=[])  # type: ignore[call-arg]

    def test_CO6_text_over_200_chars_rejected(self):
        """contradiction text > 200 chars → ValidationError (max_length=200)."""
        bad_item = {**_CONTRADICTION_ITEM, "text": "A" * 201}
        with pytest.raises(ValidationError):
            ContradictionDetectorOutput(
                contradictions=[bad_item], recommendation="Review."
            )


# ---------------------------------------------------------------------------
# §CG — contradiction_detector guardrail
# ---------------------------------------------------------------------------


class TestContradictionGuardrail:
    def test_CG1_clean_output_passes(self):
        """No banned phrases → guardrail passes silently."""
        cd_guardrail(_CD_INPUT_VALID, _CD_OUTPUT_VALID)

    def test_CG2_buy_now_in_recommendation_raises(self):
        """recommendation contains 'buy now' → AiGuardrailViolation."""
        bad_out = {**_CD_OUTPUT_VALID, "recommendation": "You should buy now."}
        with pytest.raises(AiGuardrailViolation, match="banned phrase"):
            cd_guardrail(_CD_INPUT_VALID, bad_out)

    def test_CG3_ignore_stop_in_contradiction_text_raises(self):
        """contradictions[0].text contains 'ignore stop' → AiGuardrailViolation."""
        bad_out = {
            "contradictions": [
                {"type": "other", "severity": "LOW", "text": "ignore stop and let it run."}
            ],
            "recommendation": "Proceed cautiously.",
        }
        with pytest.raises(AiGuardrailViolation, match="banned phrase"):
            cd_guardrail(_CD_INPUT_VALID, bad_out)


# ---------------------------------------------------------------------------
# news_summarizer imports (added at step 7b)
# ---------------------------------------------------------------------------

from app.ai.schemas.news_summarizer import (  # noqa: E402
    NewsSummarizerInput,
    NewsSummarizerOutput,
    NewsArticleItem,
    guardrail as ns_guardrail,
)

# ---------------------------------------------------------------------------
# Shared fixtures — news_summarizer
# ---------------------------------------------------------------------------

_ARTICLE_VALID = {
    "title": "Apple hits all-time high on strong earnings beat",
    "contentText": "Apple reported quarterly earnings well above analyst expectations.",
    "tickers": ["AAPL"],
    "publishedAt": "2026-04-28T10:00:00Z",
}

_NS_INPUT_1 = {"articles": [_ARTICLE_VALID], "windowDays": 5}

_NS_OUTPUT_VALID = {
    "catalystSummary": "Apple beat earnings; broad tech rally following strong guidance.",
    "sentiment": "positive",
    "relevantTickers": ["AAPL", "MSFT"],
    "risks": ["Macro headwinds could reverse gains"],
}


# ---------------------------------------------------------------------------
# §NI — NewsSummarizerInput
# ---------------------------------------------------------------------------


class TestNewsInput:
    def test_NI1_one_article_min_boundary(self):
        """1 article (min_length=1) → passes."""
        obj = NewsSummarizerInput(**_NS_INPUT_1)
        assert len(obj.articles) == 1

    def test_NI2_thirty_articles_max_boundary(self):
        """30 articles (max_length=30) → passes."""
        data = {"articles": [_ARTICLE_VALID] * 30, "windowDays": 5}
        obj = NewsSummarizerInput(**data)
        assert len(obj.articles) == 30

    def test_NI3_thirty_one_articles_rejected(self):
        """31 articles → ValidationError (max_length=30)."""
        data = {"articles": [_ARTICLE_VALID] * 31, "windowDays": 5}
        with pytest.raises(ValidationError):
            NewsSummarizerInput(**data)

    def test_NI4_zero_articles_rejected(self):
        """0 articles → ValidationError (min_length=1)."""
        data = {"articles": [], "windowDays": 5}
        with pytest.raises(ValidationError):
            NewsSummarizerInput(**data)

    def test_NI5_window_days_boundary_and_default(self):
        """windowDays=0 → rejected; windowDays=31 → rejected; default=5 → accepted."""
        with pytest.raises(ValidationError):
            NewsSummarizerInput(articles=[_ARTICLE_VALID], windowDays=0)
        with pytest.raises(ValidationError):
            NewsSummarizerInput(articles=[_ARTICLE_VALID], windowDays=31)
        obj = NewsSummarizerInput(articles=[_ARTICLE_VALID])
        assert obj.windowDays == 5

    def test_NI6_content_text_over_2000_rejected(self):
        """contentText > 2000 chars → ValidationError (max_length=2000)."""
        bad_article = {**_ARTICLE_VALID, "contentText": "x" * 2001}
        with pytest.raises(ValidationError):
            NewsSummarizerInput(articles=[bad_article], windowDays=5)


# ---------------------------------------------------------------------------
# §NO — NewsSummarizerOutput
# ---------------------------------------------------------------------------


class TestNewsOutput:
    def test_NO1_full_valid_output(self):
        """All fields within constraints → passes."""
        obj = NewsSummarizerOutput(**_NS_OUTPUT_VALID)
        assert obj.sentiment == "positive"
        assert len(obj.relevantTickers) == 2

    def test_NO2_invalid_sentiment_rejected(self):
        """sentiment='bullish' (non-enum) → ValidationError."""
        data = {**_NS_OUTPUT_VALID, "sentiment": "bullish"}
        with pytest.raises(ValidationError):
            NewsSummarizerOutput(**data)

    def test_NO3_eleven_relevant_tickers_rejected(self):
        """relevantTickers with 11 items → ValidationError (max_length=10)."""
        data = {**_NS_OUTPUT_VALID, "relevantTickers": [f"T{i}" for i in range(11)]}
        with pytest.raises(ValidationError):
            NewsSummarizerOutput(**data)

    def test_NO4_empty_risks_accepted(self):
        """risks=[] (min_length=0) → passes."""
        data = {**_NS_OUTPUT_VALID, "risks": []}
        obj = NewsSummarizerOutput(**data)
        assert obj.risks == []


# ---------------------------------------------------------------------------
# §NG — news_summarizer guardrail
# ---------------------------------------------------------------------------


class TestNewsGuardrail:
    def test_NG1_clean_output_passes(self):
        """No banned phrases → guardrail passes silently."""
        ns_guardrail(_NS_INPUT_1, _NS_OUTPUT_VALID)

    def test_NG2_banned_phrase_in_catalyst_summary_raises(self):
        """catalystSummary contains '保证收益' → AiGuardrailViolation."""
        bad_out = {**_NS_OUTPUT_VALID, "catalystSummary": "保证收益 if you follow the trend."}
        with pytest.raises(AiGuardrailViolation, match="banned phrase"):
            ns_guardrail(_NS_INPUT_1, bad_out)


# ---------------------------------------------------------------------------
# journal_assistant imports (added at step 7c)
# ---------------------------------------------------------------------------

from app.ai.schemas.journal_assistant import (  # noqa: E402
    JournalAssistantInput,
    JournalAssistantOutput,
    guardrail as ja_guardrail,
)

# ---------------------------------------------------------------------------
# Shared fixtures — journal_assistant
# ---------------------------------------------------------------------------

_TRADE_PAYLOAD = {
    "ticker": "AAPL",
    "setupType": "BREAKOUT",
    "setupQuality": "A",
    "plannedEntry": 180.00,
    "plannedStop": 175.00,
    "plannedTarget2r": 190.00,
    "actualEntry": 180.50,
    "actualExit": 189.00,
    "shares": 50,
    "entryDate": "2026-03-01",
    "exitDate": "2026-03-15",
    "holdingDays": 14,
    "rMultiple": 1.7,
    "preTradeNotes": "Breakout above 52-week high with strong volume.",
}

_MONTHLY_PAYLOAD = {
    "month": "2026-03",
    "closedTrades": [
        {"ticker": "AAPL", "setupType": "BREAKOUT", "rMultiple": 1.7, "holdingDays": 14, "closedOn": "2026-03-15"},
        {"ticker": "MSFT", "setupType": "PULLBACK", "rMultiple": -1.0, "holdingDays": 5, "closedOn": "2026-03-20"},
    ],
}

_JA_INPUT_TRADE = {"mode": "trade", "trade": _TRADE_PAYLOAD, "monthly": None}
_JA_INPUT_MONTHLY = {"mode": "monthly", "monthly": _MONTHLY_PAYLOAD, "trade": None}

_TRADE_OUTPUT = {
    "planVsActualScore": 8,
    "entryQuality": "good",
    "stopDiscipline": "good",
    "mistakes": ["Exited slightly before 2R target."],
    "lesson": "You managed the trade well but left some gains on the table. Next time hold to 2R.",
}

_MONTHLY_OUTPUT = {
    "month": "2026-03",
    "overallExpectancy": "Positive expectancy month with 1 win and 1 loss. R:R discipline was solid.",
    "ruleAdherence": 8,
    "setupPerformance": [
        {"setupType": "BREAKOUT", "tradeCount": 1, "winRate": 1.0, "avgRMultiple": 1.7},
        {"setupType": "PULLBACK", "tradeCount": 1, "winRate": 0.0, "avgRMultiple": -1.0},
    ],
    "keyLessons": ["Continue to cut losses quickly on PULLBACK setups."],
}

_JA_OUTPUT_TRADE = {"mode": "trade", "trade": _TRADE_OUTPUT, "monthly": None}
_JA_OUTPUT_MONTHLY = {"mode": "monthly", "monthly": _MONTHLY_OUTPUT, "trade": None}


# ---------------------------------------------------------------------------
# §JI — JournalAssistantInput
# ---------------------------------------------------------------------------


class TestJournalInput:
    def test_JI1_trade_mode_with_trade_payload(self):
        """mode='trade' + trade payload → passes."""
        obj = JournalAssistantInput(**_JA_INPUT_TRADE)
        assert obj.mode == "trade"
        assert obj.trade is not None
        assert obj.monthly is None

    def test_JI2_monthly_mode_with_monthly_payload(self):
        """mode='monthly' + monthly payload → passes."""
        obj = JournalAssistantInput(**_JA_INPUT_MONTHLY)
        assert obj.mode == "monthly"
        assert obj.monthly is not None
        assert obj.trade is None

    def test_JI3_trade_mode_missing_trade_payload_rejected(self):
        """mode='trade' but trade=None → ValidationError (model_validator)."""
        data = {"mode": "trade", "trade": None, "monthly": None}
        with pytest.raises(ValidationError, match="trade payload"):
            JournalAssistantInput(**data)

    def test_JI4_trade_mode_with_monthly_payload_rejected(self):
        """mode='trade' + monthly payload present → ValidationError."""
        data = {"mode": "trade", "trade": _TRADE_PAYLOAD, "monthly": _MONTHLY_PAYLOAD}
        with pytest.raises(ValidationError, match="forbids monthly"):
            JournalAssistantInput(**data)

    def test_JI5_monthly_mode_empty_closed_trades_rejected(self):
        """mode='monthly' + closedTrades=[] → ValidationError (min_length=1)."""
        bad_monthly = {**_MONTHLY_PAYLOAD, "closedTrades": []}
        data = {"mode": "monthly", "monthly": bad_monthly, "trade": None}
        with pytest.raises(ValidationError):
            JournalAssistantInput(**data)

    def test_JI6_month_missing_zero_padding_rejected(self):
        """month='2026-4' (no zero-pad) → ValidationError (pattern ^\d{4}-\d{2}$)."""
        bad_monthly = {**_MONTHLY_PAYLOAD, "month": "2026-4"}
        data = {"mode": "monthly", "monthly": bad_monthly, "trade": None}
        with pytest.raises(ValidationError):
            JournalAssistantInput(**data)


# ---------------------------------------------------------------------------
# §JO — JournalAssistantOutput
# ---------------------------------------------------------------------------


class TestJournalOutput:
    def test_JO1_trade_mode_output_valid(self):
        """mode='trade' + trade output → passes."""
        obj = JournalAssistantOutput(**_JA_OUTPUT_TRADE)
        assert obj.mode == "trade"
        assert obj.trade is not None

    def test_JO2_trade_mode_with_monthly_payload_rejected(self):
        """mode='trade' output + monthly payload present → ValidationError (model_validator)."""
        bad = {"mode": "trade", "trade": _TRADE_OUTPUT, "monthly": _MONTHLY_OUTPUT}
        with pytest.raises(ValidationError):
            JournalAssistantOutput(**bad)

    def test_JO3_plan_vs_actual_score_11_rejected(self):
        """planVsActualScore=11 → ValidationError (le=10)."""
        bad_trade = {**_TRADE_OUTPUT, "planVsActualScore": 11}
        data = {"mode": "trade", "trade": bad_trade, "monthly": None}
        with pytest.raises(ValidationError):
            JournalAssistantOutput(**data)


# ---------------------------------------------------------------------------
# §JG — journal_assistant guardrail
# ---------------------------------------------------------------------------


class TestJournalGuardrail:
    def test_JG1_buy_now_in_trade_lesson_raises(self):
        """trade.lesson contains 'buy now' → AiGuardrailViolation."""
        bad_out = {
            "mode": "trade",
            "trade": {**_TRADE_OUTPUT, "lesson": "You should buy now on every dip."},
            "monthly": None,
        }
        with pytest.raises(AiGuardrailViolation, match="banned phrase"):
            ja_guardrail(_JA_INPUT_TRADE, bad_out)

    def test_JG2_banned_phrase_in_monthly_key_lessons_raises(self):
        """monthly.keyLessons contains '忽略止损' → AiGuardrailViolation."""
        bad_out = {
            "mode": "monthly",
            "monthly": {**_MONTHLY_OUTPUT, "keyLessons": ["忽略止损 when trend is strong."]},
            "trade": None,
        }
        with pytest.raises(AiGuardrailViolation, match="banned phrase"):
            ja_guardrail(_JA_INPUT_MONTHLY, bad_out)


# ---------------------------------------------------------------------------
# §R — REGISTRY + routing tier (added at step 7d)
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_R1_get_schemas_contradiction_detector(self):
        """get_schemas('contradiction_detector') returns a SchemaPair."""
        from app.ai.schemas import get_schemas, SchemaPair

        pair = get_schemas("contradiction_detector")
        assert isinstance(pair, SchemaPair)
        assert pair.input_schema is ContradictionDetectorInput
        assert pair.output_schema is ContradictionDetectorOutput

    def test_R2_get_schemas_news_summarizer(self):
        """get_schemas('news_summarizer') returns a SchemaPair."""
        from app.ai.schemas import get_schemas, SchemaPair

        pair = get_schemas("news_summarizer")
        assert isinstance(pair, SchemaPair)
        assert pair.input_schema is NewsSummarizerInput
        assert pair.output_schema is NewsSummarizerOutput

    def test_R3_get_schemas_journal_assistant(self):
        """get_schemas('journal_assistant') returns a SchemaPair."""
        from app.ai.schemas import get_schemas, SchemaPair

        pair = get_schemas("journal_assistant")
        assert isinstance(pair, SchemaPair)
        assert pair.input_schema is JournalAssistantInput
        assert pair.output_schema is JournalAssistantOutput

    def test_R4_guardrail_hooks_all_three_registered(self):
        """guardrail._HOOKS contains entries for all three F211 task_types."""
        from app.ai import guardrail as gr

        for task_type in ("contradiction_detector", "news_summarizer", "journal_assistant"):
            assert task_type in gr._HOOKS, f"missing hook for {task_type}"
            assert callable(gr._HOOKS[task_type])

    def test_R5_contradiction_detector_resolves_default(self):
        """routing.resolve_tier('contradiction_detector') → 'default'."""
        from app.ai.routing import resolve_tier

        assert resolve_tier("contradiction_detector") == "default"

    def test_R6_news_summarizer_resolves_default(self):
        """routing.resolve_tier('news_summarizer') → 'default'."""
        from app.ai.routing import resolve_tier

        assert resolve_tier("news_summarizer") == "default"

    def test_R7_journal_assistant_resolves_complex(self):
        """routing.resolve_tier('journal_assistant') → 'complex'."""
        from app.ai.routing import resolve_tier

        assert resolve_tier("journal_assistant") == "complex"
