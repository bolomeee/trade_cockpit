"""Market Narrator task schema (F209-a).

Input: regime + marketScore + subscores + sectors
Output: headline + summary + riskPosture + preferredSetups + avoid + warnings
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.ai.errors import AiGuardrailViolation

SCHEMA_VERSION = "v1"

SYSTEM_PROMPT = """You are a professional equity market analyst assistant.
Given current market regime data, produce a concise market narrative.

Rules:
- headline: one sentence, ≤ 120 chars, actionable but not directive
- summary: 2-4 sentences, ≤ 600 chars, describe conditions and implications
- riskPosture: one of aggressive / balanced / cautious / defensive
- preferredSetups: up to 5 setup types that fit current conditions
- avoid: up to 5 setup types or sector exposures to avoid
- warnings: up to 5 risk flags or tail-risk reminders

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


class MarketNarratorSubscores(BaseModel):
    spyTrend: int = Field(ge=0)
    qqqTrend: int = Field(ge=0)
    iwmBreadth: int = Field(ge=0)
    sectorParticipation: int = Field(ge=0)
    riskAppetite: int = Field(ge=0)
    volatilityStress: int = Field(ge=0)
    model_config = {"extra": "forbid"}


class MarketNarratorSector(BaseModel):
    symbol: str
    closePct: float
    state: Literal["Strong", "Neutral", "Weak"]
    model_config = {"extra": "forbid"}


class MarketNarratorInput(BaseModel):
    regime: Literal["RISK_ON", "CONSTRUCTIVE", "NEUTRAL", "DEFENSIVE", "RISK_OFF"]
    marketScore: int = Field(ge=0, le=100)
    subscores: MarketNarratorSubscores
    sectors: list[MarketNarratorSector]
    model_config = {"extra": "forbid"}


class MarketNarratorOutput(BaseModel):
    headline: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=600)
    riskPosture: Literal["aggressive", "balanced", "cautious", "defensive"]
    preferredSetups: list[str] = Field(min_length=0, max_length=5)
    avoid: list[str] = Field(min_length=0, max_length=5)
    warnings: list[str] = Field(min_length=0, max_length=5)
    model_config = {"extra": "forbid"}


def guardrail(input_dict: dict, output_dict: dict) -> None:
    """Scan output text fields for BANNED_PHRASES; raise AiGuardrailViolation on hit."""
    parts: list[str] = []
    parts.append(output_dict.get("headline", "") or "")
    parts.append(output_dict.get("summary", "") or "")
    for field in ("preferredSetups", "avoid", "warnings"):
        items = output_dict.get(field) or []
        if isinstance(items, list):
            parts.extend(str(item) for item in items)

    combined = " ".join(parts).lower()
    for phrase in BANNED_PHRASES:
        if phrase.lower() in combined:
            raise AiGuardrailViolation(f"banned phrase: {phrase}")
