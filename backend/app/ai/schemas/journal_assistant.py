"""Journal Assistant task schema (F211-a1, complex tier).

Dual-mode: trade (per-trade post-exit review) + monthly (strategy audit).
Single task_type, single REGISTRY entry — mode field discriminates payload.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.ai.errors import AiGuardrailViolation

SCHEMA_VERSION = "v1"

SYSTEM_PROMPT = """You are a trading coach conducting a post-trade or monthly strategy review.

For mode='trade': analyze plan vs actual execution and provide attribution.
For mode='monthly': audit overall strategy performance across all closed trades.

Rules (trade mode):
- planVsActualScore: integer 1-10 (10 = perfect execution)
- entryQuality / stopDiscipline: good / fair / poor
- mistakes: 0-5 specific execution errors
- lesson: 1-3 sentences in second person (≤500 chars)

Rules (monthly mode):
- overallExpectancy: 1-3 sentence summary (≤200 chars)
- ruleAdherence: integer 1-10
- setupPerformance: per-setup breakdown (0-10 entries)
- keyLessons: 0-5 actionable lessons in second person

General rules:
- mode field in output must echo the input mode exactly
- Do not produce output for the other mode
- Use second person ("You over-traded...") in lesson/keyLessons

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

_SETUP_TYPE = Literal["BREAKOUT", "PULLBACK", "RECLAIM", "EARNINGS_DRIFT", "EXTENDED", "BROKEN", "NONE"]


# ─── Sub-payloads: input ─────────────────────────────────────────────────────


class TradeReviewPayload(BaseModel):
    ticker: str = Field(min_length=1, max_length=10, pattern=r"^[A-Z][A-Z0-9.\-]*$")
    setupType: _SETUP_TYPE | None = None
    setupQuality: Literal["A", "B", "C"] | None = None
    plannedEntry: float = Field(gt=0)
    plannedStop: float = Field(gt=0)
    plannedTarget2r: float | None = Field(default=None, gt=0)
    actualEntry: float = Field(gt=0)
    actualExit: float = Field(gt=0)
    shares: int = Field(ge=1)
    entryDate: str = Field(min_length=10, max_length=10)
    exitDate: str = Field(min_length=10, max_length=10)
    holdingDays: int = Field(ge=0)
    rMultiple: float
    preTradeNotes: str | None = Field(default=None, max_length=1000)
    model_config = {"extra": "forbid"}


class ClosedTradeBrief(BaseModel):
    ticker: str
    setupType: _SETUP_TYPE | None = None
    rMultiple: float
    holdingDays: int = Field(ge=0)
    closedOn: str = Field(min_length=10, max_length=10)
    model_config = {"extra": "forbid"}


class MonthlyReviewPayload(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    closedTrades: list[ClosedTradeBrief] = Field(min_length=1, max_length=100)
    model_config = {"extra": "forbid"}


# ─── Root input ──────────────────────────────────────────────────────────────


class JournalAssistantInput(BaseModel):
    mode: Literal["trade", "monthly"]
    trade: TradeReviewPayload | None = None
    monthly: MonthlyReviewPayload | None = None
    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _check_mode_payload(self) -> "JournalAssistantInput":
        if self.mode == "trade":
            if self.trade is None:
                raise ValueError("mode='trade' requires trade payload")
            if self.monthly is not None:
                raise ValueError("mode='trade' forbids monthly payload")
        else:
            if self.monthly is None:
                raise ValueError("mode='monthly' requires monthly payload")
            if self.trade is not None:
                raise ValueError("mode='monthly' forbids trade payload")
        return self


# ─── Sub-payloads: output ─────────────────────────────────────────────────────


class TradeReviewOutput(BaseModel):
    planVsActualScore: int = Field(ge=1, le=10)
    entryQuality: Literal["good", "fair", "poor"]
    stopDiscipline: Literal["good", "fair", "poor"]
    mistakes: list[str] = Field(min_length=0, max_length=5)
    lesson: str = Field(min_length=1, max_length=500)
    model_config = {"extra": "forbid"}


class SetupPerformance(BaseModel):
    setupType: str
    tradeCount: int = Field(ge=1)
    winRate: float = Field(ge=0, le=1)
    avgRMultiple: float
    model_config = {"extra": "forbid"}


class MonthlyReviewOutput(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    overallExpectancy: str = Field(min_length=1, max_length=200)
    ruleAdherence: int = Field(ge=1, le=10)
    setupPerformance: list[SetupPerformance] = Field(min_length=0, max_length=10)
    keyLessons: list[str] = Field(min_length=0, max_length=5)
    model_config = {"extra": "forbid"}


# ─── Root output ─────────────────────────────────────────────────────────────


class JournalAssistantOutput(BaseModel):
    mode: Literal["trade", "monthly"]
    trade: TradeReviewOutput | None = None
    monthly: MonthlyReviewOutput | None = None
    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _check_output_mode(self) -> "JournalAssistantOutput":
        if self.mode == "trade" and (self.trade is None or self.monthly is not None):
            raise ValueError("mode='trade' output requires trade payload only")
        if self.mode == "monthly" and (self.monthly is None or self.trade is not None):
            raise ValueError("mode='monthly' output requires monthly payload only")
        return self


# ─── Guardrail ────────────────────────────────────────────────────────────────


def guardrail(input_dict: dict, output_dict: dict) -> None:
    """Scan trade.lesson + trade.mistakes[] + monthly.overallExpectancy + monthly.keyLessons[]."""
    parts: list[str] = []

    trade = output_dict.get("trade") or {}
    if isinstance(trade, dict):
        parts.append(trade.get("lesson", "") or "")
        for item in trade.get("mistakes") or []:
            parts.append(str(item))

    monthly = output_dict.get("monthly") or {}
    if isinstance(monthly, dict):
        parts.append(monthly.get("overallExpectancy", "") or "")
        for item in monthly.get("keyLessons") or []:
            parts.append(str(item))

    combined = " ".join(parts).lower()
    for phrase in BANNED_PHRASES:
        if phrase.lower() in combined:
            raise AiGuardrailViolation(f"banned phrase: {phrase}")
