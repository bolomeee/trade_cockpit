"""Trade Plan task schema (F210-a, critical tier).

Input: full Decision quote (ticker + entry/stop/target + size + risk + earnings + hash)
Output: memo + management list + echoed entry/stop/size (must match input — D068 guardrail)
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.ai.errors import AiGuardrailViolation
from app.services.cockpit.cockpit_params import DECISION

SCHEMA_VERSION = "v1"
HASH_PRICE_DECIMALS: int = DECISION.HASH_PRICE_DECIMALS  # 2; single source — no drift

SYSTEM_PROMPT = """You are an equity trade planning assistant for a slow-trading system.
You receive a fully deterministic trade quote (entry / stop / size already computed).
You MUST NOT alter entry / stop / size — echo them verbatim. Add narrative memo and
management rules only.

Rules:
- memo: 2-4 sentences, ≤ 600 chars; cite setup type and earnings risk if non-SAFE
- management: 1-5 short imperative rules (e.g. "Move stop to BE near 2R", "Trail with 21EMA")
- entry / stop / size: copy input values exactly, do not round, do not adjust
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


class TradePlanInput(BaseModel):
    ticker: str = Field(min_length=1, max_length=10, pattern=r"^[A-Z][A-Z0-9.\-]*$")
    setupType: Literal["BREAKOUT", "PULLBACK", "RECLAIM", "EARNINGS_DRIFT", "EXTENDED", "BROKEN", "NONE"]
    setupQuality: Literal["A", "B", "C"] | None = None
    entry: float = Field(gt=0)
    stop: float = Field(gt=0)
    target2r: float = Field(gt=0)
    target3r: float = Field(gt=0)
    size: int = Field(ge=1)
    rewardRisk: float = Field(ge=0)
    accountRiskPct: float = Field(ge=0, le=100)
    earningsRisk: Literal["SAFE", "CAUTION", "DANGER"]
    deterministicHash: str = Field(min_length=8)
    model_config = {"extra": "forbid"}


class TradePlanOutput(BaseModel):
    memo: str = Field(min_length=1, max_length=600)
    management: list[str] = Field(min_length=1, max_length=5)
    entry: float = Field(gt=0)
    stop: float = Field(gt=0)
    size: int = Field(ge=1)
    model_config = {"extra": "forbid"}


def guardrail(input_dict: dict, output_dict: dict) -> None:
    """D068: entry/stop/size must equal input (2-decimal aligned); BANNED_PHRASES scan."""
    in_entry = round(float(input_dict["entry"]), HASH_PRICE_DECIMALS)
    in_stop = round(float(input_dict["stop"]), HASH_PRICE_DECIMALS)
    in_size = int(input_dict["size"])

    out_entry = round(float(output_dict.get("entry", 0)), HASH_PRICE_DECIMALS)
    out_stop = round(float(output_dict.get("stop", 0)), HASH_PRICE_DECIMALS)
    out_size = int(output_dict.get("size", 0))

    if out_entry != in_entry:
        raise AiGuardrailViolation(
            f"trade_plan entry mismatch: input={in_entry} output={out_entry}"
        )
    if out_stop != in_stop:
        raise AiGuardrailViolation(
            f"trade_plan stop mismatch: input={in_stop} output={out_stop}"
        )
    if out_size != in_size:
        raise AiGuardrailViolation(
            f"trade_plan size mismatch: input={in_size} output={out_size}"
        )

    parts: list[str] = [output_dict.get("memo", "") or ""]
    items = output_dict.get("management") or []
    if isinstance(items, list):
        parts.extend(str(x) for x in items)
    combined = " ".join(parts).lower()
    for phrase in BANNED_PHRASES:
        if phrase.lower() in combined:
            raise AiGuardrailViolation(f"banned phrase: {phrase}")
