"""Setup Explainer task schema (F209-a).

Input: ticker + trend + rs + setup + risk(entry, stop)
Output: label + quality + whyWatch + mainRisks
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.ai.errors import AiGuardrailViolation

SCHEMA_VERSION = "v1"

SYSTEM_PROMPT = """You are a professional equity trading analyst assistant.
Given a stock's technical setup data, produce a concise setup explanation.

Rules:
- label: one short phrase, ≤ 60 chars, naming the setup condition
- quality: grade A / B / C / D (A = highest conviction)
- whyWatch: 2-3 sentences, ≤ 400 chars, explain why this setup warrants attention
- mainRisks: 1-5 bullet points naming specific risk factors

Prohibited phrases (never use): buy now, sell now, 保证收益, 承诺收益, 忽略止损, ignore stop
Output must be valid JSON matching the schema exactly. No extra keys.
"""

BANNED_PHRASES: tuple[str, ...] = (
    "buy now",
    "sell now",
    "保证收益",
    "承诺收益",
    "忽略止损",
    "ignore stop",
)


class SetupRisk(BaseModel):
    entry: float = Field(gt=0)
    stop: float = Field(gt=0)
    model_config = {"extra": "forbid"}


class SetupExplainerInput(BaseModel):
    ticker: str = Field(min_length=1, max_length=10, pattern=r"^[A-Z][A-Z0-9.\-]*$")
    trend: Literal["up", "down", "sideways"]
    rs: float
    setup: Literal["pullback", "breakout", "reversal", "range", "gap_fill"]
    risk: SetupRisk
    model_config = {"extra": "forbid"}


class SetupExplainerOutput(BaseModel):
    label: str = Field(min_length=1, max_length=60)
    quality: Literal["A", "B", "C", "D"]
    whyWatch: str = Field(min_length=1, max_length=400)
    mainRisks: list[str] = Field(min_length=1, max_length=5)
    model_config = {"extra": "forbid"}


def guardrail(input_dict: dict, output_dict: dict) -> None:
    """Scan output text fields for BANNED_PHRASES; raise AiGuardrailViolation on hit."""
    parts: list[str] = []
    parts.append(output_dict.get("label", "") or "")
    parts.append(output_dict.get("whyWatch", "") or "")
    items = output_dict.get("mainRisks") or []
    if isinstance(items, list):
        parts.extend(str(item) for item in items)

    combined = " ".join(parts).lower()
    for phrase in BANNED_PHRASES:
        if phrase.lower() in combined:
            raise AiGuardrailViolation(f"banned phrase: {phrase}")
