"""News Summarizer task schema (F211-a1, default tier).

Input: list of news articles (title + contentText + tickers + publishedAt)
Output: catalystSummary + sentiment + relevantTickers + risks
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.ai.errors import AiGuardrailViolation

SCHEMA_VERSION = "v1"

SYSTEM_PROMPT = """You are a financial news analyst. Synthesize a batch of news articles into a structured summary.

Rules:
- catalystSummary: 1-3 sentence paragraph (≤500 chars) describing the key market catalyst or event
- sentiment: overall market sentiment — positive, neutral, or negative
- relevantTickers: up to 10 tickers most relevant to the main catalyst (not just most-mentioned)
- risks: 0-5 specific risk or warning items from the news

Prohibited phrases (never use): buy now, sell now, 保证收益, 承诺收益, 忽略止损, ignore stop
All text fields (catalystSummary, risks) must be written in Chinese.
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


class NewsArticleItem(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    contentText: str = Field(min_length=0, max_length=2000)
    tickers: list[str] = Field(min_length=0, max_length=20)
    publishedAt: str = Field(min_length=10, max_length=40)
    model_config = {"extra": "forbid"}


class NewsSummarizerInput(BaseModel):
    articles: list[NewsArticleItem] = Field(min_length=1, max_length=30)
    windowDays: int = Field(ge=1, le=30, default=5)
    model_config = {"extra": "forbid"}


class NewsSummarizerOutput(BaseModel):
    catalystSummary: str = Field(min_length=1, max_length=500)
    sentiment: Literal["positive", "neutral", "negative"]
    relevantTickers: list[str] = Field(min_length=0, max_length=10)
    risks: list[str] = Field(min_length=0, max_length=5)
    model_config = {"extra": "forbid"}


def guardrail(input_dict: dict, output_dict: dict) -> None:
    """Scan catalystSummary + risks[] for BANNED_PHRASES."""
    parts: list[str] = [output_dict.get("catalystSummary", "") or ""]
    for item in output_dict.get("risks") or []:
        parts.append(str(item))

    combined = " ".join(parts).lower()
    for phrase in BANNED_PHRASES:
        if phrase.lower() in combined:
            raise AiGuardrailViolation(f"banned phrase: {phrase}")
