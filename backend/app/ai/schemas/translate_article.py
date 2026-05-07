"""Translate Article task schema (F213-a, default tier + DeepSeek per-task override, D084).

Input:  title (str) + contentText (str, HTML stripped by frontend) + targetLang (zh-CN)
Output: titleZh (str) + contentZh (str)
No guardrail: translation output is a structural mapping of source text;
BANNED_PHRASES are not applicable and would cause false positives.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = "v1"

SYSTEM_PROMPT = """你是专业的金融新闻翻译员。将输入的英文新闻翻译成简洁、准确的中文。

严格规则：
1. 公司名、人名、机构名、股票代码（如 "Microsoft"、"NASDAQ: MSFT"、"Tigress Financial"）必须保留原文，不得意译。
2. 数字（金额、百分比、日期）保留原值，单位（%、$、亿、百万）按中文金融报道惯例转换。
3. 标题简洁有力，正文段落清晰。
4. 不增加任何注释、解释、评论或来源标注。
5. 输出必须严格遵循 JSON schema：{ "titleZh": "...", "contentZh": "..." }
"""


class TranslateArticleInput(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    contentText: str = Field(min_length=1, max_length=20000)
    targetLang: Literal["zh-CN"] = "zh-CN"
    model_config = {"extra": "forbid"}


class TranslateArticleOutput(BaseModel):
    titleZh: str = Field(min_length=1, max_length=500)
    contentZh: str = Field(min_length=1, max_length=25000)
    model_config = {"extra": "forbid"}
