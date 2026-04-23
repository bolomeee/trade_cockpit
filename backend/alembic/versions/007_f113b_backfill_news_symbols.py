"""F113-b backfill news_articles_cache.symbols with exchange-prefixed regex

Revision ID: 007_f113b_backfill_news_symbols
Revises: 006_f113a_news_articles_cache
Create Date: 2026-04-23

一次性 data migration：遍历 news_articles_cache.payload_json，用正则从
title + content_html 中抽取 `(NASDAQ: AGPU)` / `(NYSE: TORO)` 等带交易所前
缀的 ticker，合并到已有 symbols 去重保序回写。

正则内联复制，避免依赖服务层未来可能的改动——保持 migration 可重放。
"""
from __future__ import annotations

import json
import re
from typing import Sequence, Union

from alembic import op

revision: str = "007_f113b_backfill_news_symbols"
down_revision: Union[str, Sequence[str], None] = "006_f113a_news_articles_cache"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_EXCHANGE_PREFIXED_RE = re.compile(
    r"\(\s*"
    r"(?i:NASDAQ(?:CM)?|NYSE(?:ARCA)?|AMEX|CBOE|BATS|NMS|OTC(?:QB|QX|BB)?)"
    r"\s*:\s*"
    r"([A-Z][A-Z0-9.-]{0,5})"
    r"\s*\)"
)


def _extract(text: str) -> list[str]:
    if not isinstance(text, str) or not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in _EXCHANGE_PREFIXED_RE.finditer(text):
        sym = m.group(1).strip()
        if sym and sym not in seen:
            seen.add(sym)
            out.append(sym)
    return out


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.exec_driver_sql(
        "SELECT id, payload_json FROM news_articles_cache"
    ).fetchall()

    updated = 0
    for row_id, payload_json in rows:
        try:
            data = json.loads(payload_json)
        except (TypeError, ValueError):
            continue

        title = data.get("title") or ""
        content = data.get("content_html") or ""
        existing = list(data.get("symbols") or [])
        extra = _extract(f"{title} {content}")

        seen: set[str] = set(existing)
        merged = list(existing)
        changed = False
        for sym in extra:
            if sym not in seen:
                seen.add(sym)
                merged.append(sym)
                changed = True

        if not changed:
            continue

        data["symbols"] = merged
        conn.exec_driver_sql(
            "UPDATE news_articles_cache SET payload_json = :p WHERE id = :i",
            {"p": json.dumps(data), "i": row_id},
        )
        updated += 1

    print(f"[007_f113b] backfilled {updated}/{len(rows)} news cache rows")


def downgrade() -> None:
    # Data-only migration; symbols enrichment is not reversible without
    # tracking original values. Intentionally no-op.
    pass
