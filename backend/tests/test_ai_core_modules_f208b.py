"""F208-b: unit + integration tests for app.ai core modules (errors/routing/memo_repo/budget)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.ai.budget import assert_within_budget, month_to_date_cost
from app.ai.errors import (
    AiBudgetExceeded,
    AiError,
    AiGuardrailViolation,
    AiProviderError,
    AiSchemaError,
)
from app.ai.memo_repo import AiMemoRepository, compute_input_hash
from app.ai.routing import ResolvedRoute, known_task_types, resolve, resolve_model, resolve_tier
from app.config import settings
from app.models.ai_memo import AiMemo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 4, 25, 12, 0, 0, tzinfo=timezone.utc)

_WRITE_KWARGS = dict(
    task_type="market_narrator",
    input_dict={"symbol": "AAPL"},
    output_dict={"summary": "bullish"},
    schema_version="v1",
    model_used="gpt-5.4-mini",
    tier="default",
    tokens_in=100,
    tokens_out=50,
    cost_usd=Decimal("0.001234"),
    latency_ms=420,
)


# ---------------------------------------------------------------------------
# errors — hierarchy
# ---------------------------------------------------------------------------


def test_error_hierarchy():
    assert issubclass(AiError, Exception)
    for cls in (AiProviderError, AiSchemaError, AiBudgetExceeded, AiGuardrailViolation):
        assert issubclass(cls, AiError), f"{cls.__name__} must inherit AiError"


# ---------------------------------------------------------------------------
# compute_input_hash
# ---------------------------------------------------------------------------


def test_input_hash_is_order_invariant():
    h1 = compute_input_hash({"a": 1, "b": 2})
    h2 = compute_input_hash({"b": 2, "a": 1})
    assert h1 == h2
    assert len(h1) == 64
    assert h1.isalnum()


def test_input_hash_distinguishes_values():
    assert compute_input_hash({"a": 1}) != compute_input_hash({"a": 2})
    # type-sensitive: int 1 ≠ str "1"
    assert compute_input_hash({"a": 1}) != compute_input_hash({"a": "1"})


def test_input_hash_stable_with_unicode():
    d = {"名前": "テスト", "value": "中文"}
    assert compute_input_hash(d) == compute_input_hash(d)
    assert len(compute_input_hash(d)) == 64


# ---------------------------------------------------------------------------
# routing
# ---------------------------------------------------------------------------


def test_routing_seven_task_types_mapped():
    types = known_task_types()
    # 8 production types + "echo" test-only entry (F208-c, not in API-CONTRACT)
    # F213-a added translate_article (default tier, D084)
    production_types = [t for t in types if t != "echo"]
    assert len(production_types) == 8
    expected_tiers = {
        "market_narrator": "critical",
        "setup_explainer": "default",
        "candidate_ranker": "critical",
        "trade_plan": "critical",
        "contradiction_detector": "critical",
        "news_summarizer": "critical",
        "journal_assistant": "complex",
        "translate_article": "default",
    }
    for task, expected_tier in expected_tiers.items():
        route = resolve(task)
        assert isinstance(route, ResolvedRoute)
        assert route.tier == expected_tier, f"{task}: expected tier {expected_tier!r}, got {route.tier!r}"
        assert isinstance(route.model, str) and route.model
        assert route.base_url is None
        assert route.api_key == settings.openai_api_key
        assert route.custom_input_cost is None


def test_routing_unknown_task_type_raises():
    with pytest.raises(ValueError, match="foo"):
        resolve("foo")


def test_routing_uses_settings_models(monkeypatch):
    monkeypatch.setattr(settings, "ai_model_critical", "claude-sonnet-4-6")
    route = resolve("trade_plan")
    assert route.tier == "critical"
    assert route.model == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# AiMemoRepository
# ---------------------------------------------------------------------------


def test_memo_write_returns_id_and_persists(db_session):
    repo = AiMemoRepository(db_session)
    memo_id = repo.write(**_WRITE_KWARGS)
    assert isinstance(memo_id, int) and memo_id > 0

    row = db_session.get(AiMemo, memo_id)
    assert row.task_type == "market_narrator"
    assert row.schema_version == "v1"
    assert row.tokens_in == 100
    assert row.tokens_out == 50
    assert row.latency_ms == 420
    assert Decimal(str(row.cost_usd)) == Decimal("0.001234")


def test_memo_find_cached_hit_within_ttl(db_session):
    repo = AiMemoRepository(db_session)
    written_at = _NOW - timedelta(hours=1)
    memo = AiMemo(
        task_type="market_narrator",
        input_hash=compute_input_hash({"symbol": "AAPL"}),
        input_json='{"symbol":"AAPL"}',
        output_json='{"summary":"bullish"}',
        schema_version="v1",
        model_used="gpt-5.4-mini",
        tier="default",
        tokens_in=10,
        tokens_out=5,
        cost_usd=Decimal("0.0001"),
        latency_ms=100,
        created_at=written_at,
    )
    db_session.add(memo)
    db_session.commit()

    result = repo.find_cached(
        task_type="market_narrator",
        input_hash=compute_input_hash({"symbol": "AAPL"}),
        schema_version="v1",
        ttl_hours=24,
        now=_NOW,
    )
    assert result is not None
    assert result.id == memo.id


def test_memo_find_cached_miss_after_ttl(db_session):
    repo = AiMemoRepository(db_session)
    old_time = _NOW - timedelta(hours=25)
    memo = AiMemo(
        task_type="market_narrator",
        input_hash=compute_input_hash({"symbol": "AAPL"}),
        input_json='{"symbol":"AAPL"}',
        output_json='{"summary":"old"}',
        schema_version="v1",
        model_used="gpt-5.4-mini",
        tier="default",
        tokens_in=10,
        tokens_out=5,
        cost_usd=Decimal("0.0001"),
        latency_ms=100,
        created_at=old_time,
    )
    db_session.add(memo)
    db_session.commit()

    result = repo.find_cached(
        task_type="market_narrator",
        input_hash=compute_input_hash({"symbol": "AAPL"}),
        schema_version="v1",
        ttl_hours=24,
        now=_NOW,
    )
    assert result is None


def test_memo_find_cached_miss_on_schema_version_mismatch(db_session):
    repo = AiMemoRepository(db_session)
    memo = AiMemo(
        task_type="market_narrator",
        input_hash=compute_input_hash({"symbol": "AAPL"}),
        input_json='{"symbol":"AAPL"}',
        output_json='{"summary":"v1 output"}',
        schema_version="v1",
        model_used="gpt-5.4-mini",
        tier="default",
        tokens_in=10,
        tokens_out=5,
        cost_usd=Decimal("0.0001"),
        latency_ms=100,
        created_at=_NOW - timedelta(hours=1),
    )
    db_session.add(memo)
    db_session.commit()

    result = repo.find_cached(
        task_type="market_narrator",
        input_hash=compute_input_hash({"symbol": "AAPL"}),
        schema_version="v2",
        ttl_hours=24,
        now=_NOW,
    )
    assert result is None


def test_memo_find_cached_returns_latest_when_multiple(db_session):
    repo = AiMemoRepository(db_session)
    h = compute_input_hash({"symbol": "AAPL"})
    older = AiMemo(
        task_type="market_narrator",
        input_hash=h,
        input_json='{"symbol":"AAPL"}',
        output_json='{"summary":"older"}',
        schema_version="v1",
        model_used="gpt-5.4-mini",
        tier="default",
        tokens_in=10,
        tokens_out=5,
        cost_usd=Decimal("0.0001"),
        latency_ms=100,
        created_at=_NOW - timedelta(hours=5),
    )
    newer = AiMemo(
        task_type="market_narrator",
        input_hash=h,
        input_json='{"symbol":"AAPL"}',
        output_json='{"summary":"newer"}',
        schema_version="v1",
        model_used="gpt-5.4-mini",
        tier="default",
        tokens_in=10,
        tokens_out=5,
        cost_usd=Decimal("0.0001"),
        latency_ms=100,
        created_at=_NOW - timedelta(hours=2),
    )
    db_session.add_all([older, newer])
    db_session.commit()

    result = repo.find_cached(
        task_type="market_narrator",
        input_hash=h,
        schema_version="v1",
        ttl_hours=24,
        now=_NOW,
    )
    assert result is not None
    assert result.output_json == '{"summary":"newer"}'


def test_memo_write_uses_canonical_input_json(db_session):
    repo = AiMemoRepository(db_session)
    memo_id = repo.write(
        task_type="market_narrator",
        input_dict={"b": 2, "a": 1},
        output_dict={"summary": "test"},
        schema_version="v1",
        model_used="gpt-5.4-mini",
        tier="default",
        tokens_in=10,
        tokens_out=5,
        cost_usd=Decimal("0.0001"),
        latency_ms=100,
    )
    row = db_session.get(AiMemo, memo_id)
    assert row.input_json == '{"a":1,"b":2}'
    assert row.input_hash == compute_input_hash({"a": 1, "b": 2})


# ---------------------------------------------------------------------------
# budget
# ---------------------------------------------------------------------------


def test_budget_zero_when_no_memos(db_session):
    mtd = month_to_date_cost(db_session, now=_NOW)
    assert mtd == Decimal("0")

    result = assert_within_budget(db_session, cap_usd=10.0, now=_NOW)
    assert result == Decimal("0")


def test_budget_sums_current_month_only(db_session):
    month_start = _NOW.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    last_month = AiMemo(
        task_type="market_narrator",
        input_hash="aaa",
        input_json="{}",
        output_json="{}",
        schema_version="v1",
        model_used="gpt-5.4-mini",
        tier="default",
        tokens_in=10,
        tokens_out=5,
        cost_usd=Decimal("5.0"),
        latency_ms=100,
        created_at=month_start - timedelta(seconds=1),
    )
    this_month = AiMemo(
        task_type="market_narrator",
        input_hash="bbb",
        input_json="{}",
        output_json="{}",
        schema_version="v1",
        model_used="gpt-5.4-mini",
        tier="default",
        tokens_in=10,
        tokens_out=5,
        cost_usd=Decimal("3.0"),
        latency_ms=100,
        created_at=month_start + timedelta(hours=1),
    )
    db_session.add_all([last_month, this_month])
    db_session.commit()

    mtd = month_to_date_cost(db_session, now=_NOW)
    assert mtd == Decimal("3.0")


def test_budget_exceeds_at_exact_cap(db_session):
    month_start = _NOW.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    memo = AiMemo(
        task_type="market_narrator",
        input_hash="ccc",
        input_json="{}",
        output_json="{}",
        schema_version="v1",
        model_used="gpt-5.4-mini",
        tier="default",
        tokens_in=10,
        tokens_out=5,
        cost_usd=Decimal("10.0"),
        latency_ms=100,
        created_at=month_start + timedelta(hours=1),
    )
    db_session.add(memo)
    db_session.commit()

    with pytest.raises(AiBudgetExceeded) as exc_info:
        assert_within_budget(db_session, cap_usd=10.0, now=_NOW)
    msg = str(exc_info.value)
    assert "10" in msg


def test_budget_uses_settings_default_cap(db_session, monkeypatch):
    monkeypatch.setattr(settings, "ai_monthly_budget_usd", 1.0)
    month_start = _NOW.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    memo = AiMemo(
        task_type="market_narrator",
        input_hash="ddd",
        input_json="{}",
        output_json="{}",
        schema_version="v1",
        model_used="gpt-5.4-mini",
        tier="default",
        tokens_in=10,
        tokens_out=5,
        cost_usd=Decimal("2.0"),
        latency_ms=100,
        created_at=month_start + timedelta(hours=1),
    )
    db_session.add(memo)
    db_session.commit()

    with pytest.raises(AiBudgetExceeded):
        assert_within_budget(db_session, now=_NOW)
