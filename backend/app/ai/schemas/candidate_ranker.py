"""Candidate Ranker task schema (F210-a, critical tier).

Input: array of up to 20 setup candidates + market regime context
Output: top 3 ranked candidates with reason + action
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = "v1"

SYSTEM_PROMPT = """You are a portfolio prioritization assistant for a slow-trading system.
Given up to 20 watchlist setup candidates and current market regime, rank the TOP 3 by
trade-now priority. Use trend/RS/quality/distance/earnings_risk/ready_signal jointly;
favor ready_signal=true and earnings_risk=SAFE; avoid Risk-Off regime over-extension.

Rules:
- Output exactly 3 items, ranks 1/2/3 unique
- reason: ≤ 200 chars, one sentence per candidate
- action: enter | watch | wait (matches SetupSnapshot.suggested_action subset)
Prohibited phrases (never use): buy now, sell now, 保证收益, 承诺收益, 忽略止损, ignore stop
All text fields (reason) must be written in Chinese.
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


class CandidateInput(BaseModel):
    """Single candidate (from SetupSnapshot projection + DecisionData derivation)."""

    ticker: str = Field(min_length=1, max_length=10, pattern=r"^[A-Z][A-Z0-9.\-]*$")
    setupType: Literal["BREAKOUT", "PULLBACK", "CAPITULATION", "RECLAIM", "EARNINGS_DRIFT", "EXTENDED", "BROKEN", "NONE"]
    setupQuality: Literal["A", "B", "C"] | None = None
    trendScore: int = Field(ge=0, le=5)
    rsPercentile: float = Field(ge=0, le=100)
    distanceToEntryPct: float
    rewardRisk: float = Field(ge=0)
    earningsRisk: Literal["SAFE", "CAUTION", "DANGER"]
    readySignal: bool
    model_config = {"extra": "forbid"}


class CandidateRankerInput(BaseModel):
    regime: Literal["RISK_ON", "CONSTRUCTIVE", "NEUTRAL", "DEFENSIVE", "RISK_OFF"]
    regimeScore: int = Field(ge=0, le=100)
    candidates: list[CandidateInput] = Field(min_length=1, max_length=20)
    model_config = {"extra": "forbid"}


class RankedCandidate(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    rank: Literal[1, 2, 3]
    reason: str = Field(min_length=1, max_length=200)
    action: Literal["enter", "watch", "wait"]
    model_config = {"extra": "forbid"}


class CandidateRankerOutput(BaseModel):
    topCandidates: list[RankedCandidate] = Field(min_length=3, max_length=3)
    model_config = {"extra": "forbid"}
