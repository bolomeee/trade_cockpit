"""F211-a2: unit tests for per-task model override routing (D075).

Tests resolve(), _parse_overrides(), and gateway direct-cost-param injection.
Covers contract completion criteria C1–C14.
"""
from __future__ import annotations

import json

import pytest

from app.ai.routing import ResolvedRoute, resolve, resolve_tier
from app.config import settings


# ---------------------------------------------------------------------------
# Autouse fixture: reset overrides between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure ai_task_overrides_json is empty before each test."""
    monkeypatch.setattr(settings, "ai_task_overrides_json", "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_override(monkeypatch: pytest.MonkeyPatch, payload: dict) -> None:
    monkeypatch.setattr(settings, "ai_task_overrides_json", json.dumps(payload))


# ---------------------------------------------------------------------------
# C1 — Settings field exists with default ""
# ---------------------------------------------------------------------------

def test_settings_has_overrides_field() -> None:
    assert hasattr(settings, "ai_task_overrides_json")
    assert settings.ai_task_overrides_json == ""


# ---------------------------------------------------------------------------
# C2 — ResolvedRoute dataclass structure
# ---------------------------------------------------------------------------

def test_resolved_route_dataclass_is_frozen() -> None:
    r = ResolvedRoute(
        tier="default",
        model="test-model",
        base_url=None,
        api_key="key",
        custom_input_cost=None,
        custom_output_cost=None,
    )
    with pytest.raises(Exception):
        r.model = "other"  # type: ignore[misc]


def test_resolved_route_has_six_fields() -> None:
    r = ResolvedRoute(
        tier="default",
        model="test-model",
        base_url="http://localhost",
        api_key="key",
        custom_input_cost=1.0,
        custom_output_cost=2.0,
    )
    assert r.tier == "default"
    assert r.model == "test-model"
    assert r.base_url == "http://localhost"
    assert r.api_key == "key"
    assert r.custom_input_cost == 1.0
    assert r.custom_output_cost == 2.0


# ---------------------------------------------------------------------------
# C3 — No override → fallback to tier defaults
# ---------------------------------------------------------------------------

def test_resolve_no_override_falls_back_to_tier_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    route = resolve("market_narrator")
    assert route.tier == "default"
    assert route.model == settings.ai_model_default
    assert route.base_url is None
    assert route.api_key == settings.openai_api_key
    assert route.custom_input_cost is None
    assert route.custom_output_cost is None


# ---------------------------------------------------------------------------
# C4 — Full override → all fields forwarded
# ---------------------------------------------------------------------------

def test_resolve_override_full_entry_returns_all_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_override(monkeypatch, {
        "news_summarizer": {
            "model": "anthropic/claude-sonnet-4-6",
            "base_url": "https://api.anthropic.com",
            "api_key": "sk-ant-test",
            "input_cost_per_1m": 3.0,
            "output_cost_per_1m": 15.0,
        }
    })
    route = resolve("news_summarizer")
    assert route.model == "anthropic/claude-sonnet-4-6"
    assert route.base_url == "https://api.anthropic.com"
    assert route.api_key == "sk-ant-test"
    assert route.custom_input_cost == 3.0
    assert route.custom_output_cost == 15.0
    # tier preserved from _TASK_TIER
    assert route.tier == "default"


# ---------------------------------------------------------------------------
# C5 — Partial override (model only) → base_url None, api_key fallback, cost None
# ---------------------------------------------------------------------------

def test_resolve_override_partial_entry_only_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_override(monkeypatch, {"market_narrator": {"model": "openai/gpt-4o-mini"}})
    route = resolve("market_narrator")
    assert route.model == "openai/gpt-4o-mini"
    assert route.base_url is None
    assert route.api_key == settings.openai_api_key
    assert route.custom_input_cost is None
    assert route.custom_output_cost is None


# ---------------------------------------------------------------------------
# C6 — model="" → fallback to tier
# ---------------------------------------------------------------------------

def test_resolve_override_empty_model_falls_back_to_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_override(monkeypatch, {"market_narrator": {"model": "", "base_url": "http://ignored"}})
    route = resolve("market_narrator")
    assert route.model == settings.ai_model_default
    assert route.base_url is None


# ---------------------------------------------------------------------------
# C7 — Broken JSON → log warning + fallback
# ---------------------------------------------------------------------------

def test_resolve_override_invalid_json_logs_warning_and_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.ai.routing as routing_mod

    received: list[str] = []
    monkeypatch.setattr(routing_mod.log, "warning", lambda msg, *a: received.append(msg % a if a else msg))
    monkeypatch.setattr(settings, "ai_task_overrides_json", "{not valid json")
    route = resolve("market_narrator")
    assert route.model == settings.ai_model_default
    assert any("parse failed" in w for w in received)


# ---------------------------------------------------------------------------
# C8 — JSON top-level not a dict → log warning + fallback
# ---------------------------------------------------------------------------

def test_resolve_override_non_dict_json_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.ai.routing as routing_mod

    received: list[str] = []
    monkeypatch.setattr(routing_mod.log, "warning", lambda msg, *a: received.append(msg % a if a else msg))
    monkeypatch.setattr(settings, "ai_task_overrides_json", '["news_summarizer"]')
    route = resolve("market_narrator")
    assert route.model == settings.ai_model_default
    assert any("not a JSON object" in w for w in received)


# ---------------------------------------------------------------------------
# C9 — resolve("unknown_task") raises ValueError
# ---------------------------------------------------------------------------

def test_resolve_unknown_task_type_raises() -> None:
    with pytest.raises(ValueError, match="unknown task_type"):
        resolve("garbage_task_xyz")


# ---------------------------------------------------------------------------
# C9b — override provided for task_type not in _TASK_TIER still raises
# ---------------------------------------------------------------------------

def test_resolve_override_for_unmapped_task_type(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_override(monkeypatch, {"ghost_task": {"model": "openai/gpt-4o"}})
    with pytest.raises(ValueError, match="unknown task_type"):
        resolve("ghost_task")


# ---------------------------------------------------------------------------
# C10 — cost=0.0 treated as explicit (not None)
# ---------------------------------------------------------------------------

def test_resolve_override_cost_zero_treated_as_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_override(monkeypatch, {
        "journal_assistant": {
            "model": "openai/local-llama",
            "input_cost_per_1m": 0.0,
            "output_cost_per_1m": 0.0,
        }
    })
    route = resolve("journal_assistant")
    assert route.custom_input_cost == 0.0
    assert route.custom_output_cost == 0.0


# ---------------------------------------------------------------------------
# C11 — cost="3.0" string → ignored (None), type-strict
# ---------------------------------------------------------------------------

def test_resolve_override_cost_string_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_override(monkeypatch, {
        "news_summarizer": {
            "model": "openai/gpt-4o",
            "input_cost_per_1m": "3.0",
            "output_cost_per_1m": "15.0",
        }
    })
    route = resolve("news_summarizer")
    assert route.custom_input_cost is None
    assert route.custom_output_cost is None


# ---------------------------------------------------------------------------
# C12 — gateway passes input_cost_per_token / output_cost_per_token to
#        litellm.completion() when custom costs are set
# ---------------------------------------------------------------------------

def test_gateway_passes_cost_params_to_litellm_when_custom_costs_set(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """_call_litellm passes input/output_cost_per_token kwargs to completion()."""
    import types

    from app.ai import gateway as gw

    captured: dict = {}

    class FakeUsage:
        prompt_tokens = 100
        completion_tokens = 50

    class FakeChoice:
        class message:
            content = '{"dummy": true}'

    class FakeResponse:
        choices = [FakeChoice()]
        usage = FakeUsage()

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return FakeResponse()

    def fake_completion_cost(response, model=None):
        return 0.0

    fake_litellm = types.SimpleNamespace(
        completion=fake_completion,
        completion_cost=fake_completion_cost,
    )

    import sys
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    from app.ai.routing import ResolvedRoute as RR

    route = RR(
        tier="default",
        model="openai/custom-model",
        base_url="http://localhost:11434/v1",
        api_key="test-key",
        custom_input_cost=2.0,
        custom_output_cost=8.0,
    )
    gw._call_litellm(route=route, input_dict={"x": 1}, output_schema=dict)

    assert captured.get("input_cost_per_token") == pytest.approx(2.0 / 1_000_000)
    assert captured.get("output_cost_per_token") == pytest.approx(8.0 / 1_000_000)
    assert captured.get("api_base") == "http://localhost:11434/v1"


# ---------------------------------------------------------------------------
# C13 — cost both None → NO cost kwargs passed to litellm.completion()
# ---------------------------------------------------------------------------

def test_gateway_no_cost_params_when_costs_are_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys
    import types

    from app.ai import gateway as gw

    captured: dict = {}

    class FakeUsage:
        prompt_tokens = 10
        completion_tokens = 5

    class FakeChoice:
        class message:
            content = '{"dummy": true}'

    class FakeResponse:
        choices = [FakeChoice()]
        usage = FakeUsage()

    fake_litellm = types.SimpleNamespace(
        completion=lambda **kw: (captured.update(kw), FakeResponse())[1],
        completion_cost=lambda response, model=None: 0.0,
    )
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    from app.ai.routing import ResolvedRoute as RR

    route = RR(
        tier="default",
        model="openai/gpt-4o-mini",
        base_url=None,
        api_key="key",
        custom_input_cost=None,
        custom_output_cost=None,
    )
    gw._call_litellm(route=route, input_dict={"x": 1}, output_schema=dict)

    assert "input_cost_per_token" not in captured
    assert "output_cost_per_token" not in captured
