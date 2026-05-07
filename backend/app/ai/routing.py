"""task_type → tier → model_id routing (D064) + per-task override (D075, F211-a2)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Literal

from app.config import settings

log = logging.getLogger(__name__)

# task_type → tier 映射（DATA-MODEL §AiMemo task_type 枚举 + D064 tier 分配）
# 7 种 task_type；F209/F210/F211 各自对应若干
_TASK_TIER: dict[str, Literal["default", "critical", "complex"]] = {
    "market_narrator": "critical",       # F209 — upgraded to mini
    "setup_explainer": "default",        # F209
    "candidate_ranker": "critical",      # F210
    "trade_plan": "critical",            # F210
    "contradiction_detector": "critical", # F211 — upgraded to mini
    "news_summarizer": "critical",       # F211 — upgraded to mini
    "journal_assistant": "complex",      # F211
    "translate_article": "default",       # F213 — DeepSeek per-task override via AI_TASK_OVERRIDES_JSON (D084)
    "echo": "default",                    # test-only, not in API-CONTRACT §POST /api/ai/{task_type} 8 enums
}


@dataclass(frozen=True)
class ResolvedRoute:
    tier: str
    model: str
    base_url: str | None        # None = LiteLLM 默认端点
    api_key: str                # 绝不为 None，回落到 settings.openai_api_key
    custom_input_cost: float | None   # per 1M tokens; None = 使用 LiteLLM 内置
    custom_output_cost: float | None  # per 1M tokens; None = 使用 LiteLLM 内置
    json_mode: bool = False     # True = 用 {"type":"json_object"} 代替 JSON schema（D084 DeepSeek）


def known_task_types() -> tuple[str, ...]:
    return tuple(_TASK_TIER.keys())


def resolve_tier(task_type: str) -> str:
    """保留旧签名（test_ai_core_modules_f208b / test_ai_schemas_f209a/f210a/f211a1 在用）。"""
    if task_type not in _TASK_TIER:
        raise ValueError(f"unknown task_type: {task_type!r} (known={list(_TASK_TIER)})")
    return _TASK_TIER[task_type]


def resolve_model(tier: str) -> str:
    """Map tier → Settings model field. 保留旧签名（test_ai_core_modules_f208b 在用）。"""
    if tier == "default":
        return settings.ai_model_default
    if tier == "critical":
        return settings.ai_model_critical
    if tier == "complex":
        return settings.ai_model_complex
    raise ValueError(f"unknown tier: {tier!r}")


def _parse_overrides() -> dict[str, dict]:
    """Parse settings.ai_task_overrides_json; on failure log warning and return {}."""
    raw = settings.ai_task_overrides_json or ""
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        log.warning("ai_task_overrides_json parse failed, falling back to tier defaults: %s", e)
        return {}
    if not isinstance(parsed, dict):
        log.warning("ai_task_overrides_json not a JSON object, ignored")
        return {}
    return parsed


def resolve(task_type: str) -> ResolvedRoute:
    """task_type → ResolvedRoute (D064 tier 兜底 + D075 per-task override).

    Override 命中规则：task_type 在 overrides 字典内 AND override["model"] 非空 →
    使用 override 全部字段；否则走 tier 默认 + 无 base_url + settings.openai_api_key + 无自定义 cost。
    """
    tier = resolve_tier(task_type)
    overrides = _parse_overrides()
    entry = overrides.get(task_type) or {}

    model_override = (entry.get("model") or "").strip()
    if model_override:
        model = model_override
        base_url = (entry.get("base_url") or "").strip() or None
        api_key = (entry.get("api_key") or "").strip() or settings.openai_api_key
        in_cost = entry.get("input_cost_per_1m")
        out_cost = entry.get("output_cost_per_1m")
        custom_input_cost = float(in_cost) if isinstance(in_cost, (int, float)) else None
        custom_output_cost = float(out_cost) if isinstance(out_cost, (int, float)) else None
        json_mode = bool(entry.get("json_mode", False))
    else:
        model = resolve_model(tier)
        base_url = None
        api_key = settings.openai_api_key
        custom_input_cost = None
        custom_output_cost = None
        json_mode = False

    return ResolvedRoute(
        tier=tier,
        model=model,
        base_url=base_url,
        api_key=api_key,
        custom_input_cost=custom_input_cost,
        custom_output_cost=custom_output_cost,
        json_mode=json_mode,
    )
