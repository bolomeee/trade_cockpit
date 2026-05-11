"""News Summarizer task schema (F211-a1, default tier).

Input: list of news articles (title + contentText + tickers + publishedAt)
Output: catalystSummary + sentiment + relevantTickers + risks
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.ai.errors import AiGuardrailViolation

SCHEMA_VERSION = "v1"

SYSTEM_PROMPT = """你是一位专业的金融新闻分析师。请对过去1天内的新闻批量进行深入分析，生成详细的结构化摘要。

字段说明：
- catalystSummary：详细分析段落（≤1500字），需涵盖：
  ① 主要市场催化剂或事件（宏观政策/行业动态/个股异动）
  ② 各板块与重要个股的具体影响及价格含义
  ③ 相关背景与市场结构性变化
  ④ 对短线交易者的实际意义
- sentiment：整体市场情绪 — positive、neutral 或 negative
- relevantTickers：与主要催化剂最相关的股票代码（最多10个，按重要性排序，非仅频繁提及者）
- risks：具体风险或警示项（最多8条），每条需点明风险来源与潜在影响

禁用短语（绝不出现）：buy now、sell now、保证收益、承诺收益、忽略止损、ignore stop
所有文字字段（catalystSummary、risks 各条目）必须用中文撰写。
输出必须是严格匹配 schema 的有效 JSON，不含额外字段。
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
    catalystSummary: str = Field(min_length=1, max_length=1500)
    sentiment: Literal["positive", "neutral", "negative"]
    relevantTickers: list[str] = Field(min_length=0, max_length=10)
    risks: list[str] = Field(min_length=0, max_length=8)
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
