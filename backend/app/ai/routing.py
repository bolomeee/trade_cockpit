"""task_type → tier → model_id routing (D064)."""
from typing import Literal

from app.config import settings

# task_type → tier 映射（DATA-MODEL §AiMemo task_type 枚举 + D064 tier 分配）
# 7 种 task_type；F209/F210/F211 各自对应若干
_TASK_TIER: dict[str, Literal["default", "critical", "complex"]] = {
    "market_narrator": "default",        # F209
    "setup_explainer": "default",        # F209
    "candidate_ranker": "critical",      # F210
    "trade_plan": "critical",            # F210
    "contradiction_detector": "default", # F211
    "news_summarizer": "default",        # F211
    "journal_assistant": "complex",      # F211
}


def known_task_types() -> tuple[str, ...]:
    return tuple(_TASK_TIER.keys())


def resolve_tier(task_type: str) -> str:
    if task_type not in _TASK_TIER:
        raise ValueError(f"unknown task_type: {task_type!r} (known={list(_TASK_TIER)})")
    return _TASK_TIER[task_type]


def resolve_model(tier: str) -> str:
    """Map tier → Settings model field."""
    if tier == "default":
        return settings.ai_model_default
    if tier == "critical":
        return settings.ai_model_critical
    if tier == "complex":
        return settings.ai_model_complex
    raise ValueError(f"unknown tier: {tier!r}")


def resolve(task_type: str) -> tuple[str, str]:
    """Convenience: task_type → (tier, model_id)."""
    tier = resolve_tier(task_type)
    return tier, resolve_model(tier)
