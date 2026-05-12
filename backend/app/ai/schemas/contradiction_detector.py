"""Contradiction Detector task schema (F211-a1, default tier).

Input: full setup snapshot (ticker + trend + rs + setup + earnings + regime)
Output: contradictions[] (up to 5) + recommendation summary
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.ai.errors import AiGuardrailViolation

SCHEMA_VERSION = "v1"

SYSTEM_PROMPT = """You are a risk audit analyst reviewing a stock trade setup for internal contradictions.
Given the setup data, identify conflicts between technical signals, risk parameters, and market context.

Rules:
- contradictions: list of 0-5 items; each item has type, severity, and a one-line text (≤200 chars)
- severity: LOW / MEDIUM / HIGH
- recommendation: one-line summary (≤200 chars), e.g. "Delay entry N days", "Reduce size 50%", "No major contradictions"
- type must be one of: earnings_risk, reward_risk, trend_quality, extension, regime_misfit, volume, other
- If no contradictions found, output contradictions=[] and recommendation="No major contradictions"
- earningsRisk null means no earnings data; treat as not a risk factor

Prohibited phrases (never use): buy now, sell now, 保证收益, 承诺收益, 忽略止损, ignore stop
All text fields (contradictions[].text, recommendation) must be written in Chinese.
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

_SETUP_TYPE = Literal["BREAKOUT", "PULLBACK", "RECLAIM", "EARNINGS_DRIFT", "EXTENDED", "BROKEN", "NONE"]
_REGIME = Literal["RISK_ON", "CONSTRUCTIVE", "NEUTRAL", "DEFENSIVE", "RISK_OFF"]


class ContradictionDetectorInput(BaseModel):
    ticker: str = Field(min_length=1, max_length=10, pattern=r"^[A-Z][A-Z0-9.\-]*$")
    setupType: _SETUP_TYPE
    setupQuality: Literal["A", "B", "C"] | None = None
    trendScore: int = Field(ge=0, le=5)
    rsPercentile: float = Field(ge=0, le=100)
    entry: float = Field(gt=0)
    stop: float = Field(gt=0)
    target2r: float = Field(gt=0)
    rewardRisk: float = Field(ge=0)
    accountRiskPct: float = Field(ge=0, le=100)
    earningsRisk: Literal["SAFE", "CAUTION", "DANGER"] | None = None
    daysToEarnings: int | None = Field(default=None, ge=0)
    regime: _REGIME
    regimeScore: int = Field(ge=0, le=100)
    readySignal: bool
    model_config = {"extra": "forbid"}


class Contradiction(BaseModel):
    type: Literal["earnings_risk", "reward_risk", "trend_quality", "extension", "regime_misfit", "volume", "other"]
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    text: str = Field(min_length=1, max_length=200)
    model_config = {"extra": "forbid"}


class ContradictionDetectorOutput(BaseModel):
    contradictions: list[Contradiction] = Field(min_length=0, max_length=5)
    recommendation: str = Field(min_length=1, max_length=200)
    model_config = {"extra": "forbid"}


def guardrail(input_dict: dict, output_dict: dict) -> None:
    """Scan recommendation + contradictions[].text for BANNED_PHRASES."""
    parts: list[str] = [output_dict.get("recommendation", "") or ""]
    for item in output_dict.get("contradictions") or []:
        if isinstance(item, dict):
            parts.append(item.get("text", "") or "")

    combined = " ".join(parts).lower()
    for phrase in BANNED_PHRASES:
        if phrase.lower() in combined:
            raise AiGuardrailViolation(f"banned phrase: {phrase}")
