"""News service — FMP articles proxy with field normalization (F112-a).

Raw FMP `/stable/fmp-articles` payload → `NewsArticle` shape. Layer
responsibilities:
- `FmpClient.get_fmp_articles`: raw transport (rate-limited via D044)
- `NewsService.list_articles`: normalize fields + swallow per-row conversion
  errors so a single malformed article does not kill the list
- router: HTTP concerns (param validation, error mapping, envelope)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.external.fmp_client import FmpClient
from app.schemas.news import NewsArticle
from app.services.watchlist_service import APIError

DEFAULT_LIMIT: int = 20
MAX_LIMIT: int = 50


def normalize_tickers(raw: Any) -> list[str]:
    """`"NASDAQ:CYTK, NYSE:CB"` → `["CYTK", "CB"]`.

    Strips exchange prefix, trims whitespace, drops empties, preserves
    first-seen order, de-duplicates. Non-string / missing input → [].
    """
    if not isinstance(raw, str) or not raw.strip():
        return []
    seen: set[str] = set()
    out: list[str] = []
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        symbol = token.split(":", 1)[1].strip() if ":" in token else token
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        out.append(symbol)
    return out


def to_iso_datetime(raw: Any) -> str:
    """`"2026-04-21 21:11:13"` → `"2026-04-21T21:11:13Z"`.

    FMP `/fmp-articles` omits timezone; we assume UTC (matches FMP docs).
    On parse failure, return the raw string so one bad row doesn't taint
    the whole list — frontend can display best-effort.
    """
    if not isinstance(raw, str) or not raw.strip():
        return ""
    candidate = raw.strip()
    try:
        dt = datetime.strptime(candidate, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return candidate


def _to_article(row: dict[str, Any]) -> NewsArticle:
    return NewsArticle(
        title=str(row.get("title") or ""),
        published_at=to_iso_datetime(row.get("date")),
        content_html=str(row.get("content") or ""),
        symbols=normalize_tickers(row.get("tickers")),
        image_url=row.get("image") or None,
        url=row.get("link") or None,
        author=row.get("author") or None,
        site=row.get("site") or None,
    )


class NewsService:
    def __init__(self, fmp: FmpClient) -> None:
        self._fmp = fmp

    def list_articles(self, limit: int = DEFAULT_LIMIT) -> list[NewsArticle]:
        try:
            raw = self._fmp.get_fmp_articles(page=0, limit=limit)
        except (httpx.HTTPError, httpx.HTTPStatusError) as exc:
            raise APIError(
                "EXTERNAL_API_ERROR",
                f"FMP articles upstream failed: {exc}",
                502,
            ) from exc

        out: list[NewsArticle] = []
        for row in raw:
            if not isinstance(row, dict):
                continue
            out.append(_to_article(row))
        return out
