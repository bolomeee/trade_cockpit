"""News service — FMP articles proxy with cache layer (F113-a).

Behavior:
  window="calendar-1d"  Cache-first: read today+yesterday from DB; fetch FMP
                        only if coverage insufficient; upsert results.
  window="none"         Direct FMP, no cache (F112-a compat / skip-cache).
  since=<datetime>      Incremental: paginate FMP until date <= since or
                        FMP_INCREMENTAL_MAX_PAGES reached; upsert; return
                        only articles newer than since.

When db is None (legacy / test path) all requests fall through to direct FMP.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.external.fmp_client import FmpClient
from app.repositories import news_cache_repository as cache_repo
from app.schemas.news import NewsArticle, NewsListResponseMeta
from app.services.watchlist_service import APIError

logger = logging.getLogger(__name__)

DEFAULT_LIMIT: int = 20
MAX_LIMIT: int = 200
FMP_INCREMENTAL_MAX_PAGES: int = 5


@dataclass
class ArticleListResult:
    articles: list[NewsArticle] = field(default_factory=list)
    meta: NewsListResponseMeta = field(
        default_factory=lambda: NewsListResponseMeta(
            cache_hit=False, fmp_calls=0, truncated=False
        )
    )


def normalize_tickers(raw: Any) -> list[str]:
    """`"NASDAQ:CYTK, NYSE:CB"` → `["CYTK", "CB"]`."""
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


_EXCHANGE_PREFIXED_RE = re.compile(
    r"\(\s*"
    r"(?i:NASDAQ(?:CM)?|NYSE(?:ARCA)?|AMEX|CBOE|BATS|NMS|OTC(?:QB|QX|BB)?)"
    r"\s*:\s*"
    r"([A-Z][A-Z0-9.-]{0,5})"
    r"\s*\)"
)


def extract_exchange_prefixed_tickers(text: Any) -> list[str]:
    """Extract `(NASDAQ: AGPU)` / `(NYSE: TORO)` patterns from free text.

    Ticker part is case-sensitive uppercase (so `(NASDAQ: agpu)` is rejected
    as likely not a real ticker reference). Exchange prefix is case-insensitive.
    Returns dedup list preserving first-seen order.
    """
    if not isinstance(text, str) or not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for match in _EXCHANGE_PREFIXED_RE.finditer(text):
        sym = match.group(1).strip()
        if sym and sym not in seen:
            seen.add(sym)
            out.append(sym)
    return out


def to_iso_datetime(raw: Any) -> str:
    """`"2026-04-21 21:11:13"` → `"2026-04-21T21:11:13Z"`.

    FMP `/fmp-articles` omits timezone; we assume UTC.
    Returns raw string on parse failure so one bad row doesn't kill the list.
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
    title = str(row.get("title") or "")
    content = str(row.get("content") or "")
    fmp_symbols = normalize_tickers(row.get("tickers"))
    extra_symbols = extract_exchange_prefixed_tickers(f"{title} {content}")
    seen: set[str] = set()
    merged: list[str] = []
    for sym in (*fmp_symbols, *extra_symbols):
        if sym not in seen:
            seen.add(sym)
            merged.append(sym)
    return NewsArticle(
        title=title,
        published_at=to_iso_datetime(row.get("date")),
        content_html=content,
        symbols=merged,
        image_url=row.get("image") or None,
        url=row.get("link") or None,
        author=row.get("author") or None,
        site=row.get("site") or None,
    )


def _fmp_date_to_naive_utc(fmp_date_str: Any) -> datetime | None:
    """Parse FMP 'date' field to naive UTC datetime for comparison."""
    if not isinstance(fmp_date_str, str):
        return None
    try:
        return datetime.strptime(fmp_date_str.strip()[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


class NewsService:
    def __init__(self, fmp: FmpClient, db: Session | None = None) -> None:
        self._fmp = fmp
        self._db = db

    def list_articles(
        self,
        limit: int = DEFAULT_LIMIT,
        since: datetime | None = None,
        window: str = "calendar-1d",
    ) -> ArticleListResult:
        # Normalize since to naive UTC if timezone-aware
        if since is not None and since.tzinfo is not None:
            since = since.replace(tzinfo=None)

        if self._db is None or window == "none":
            return self._fetch_direct(limit)

        if since is not None:
            return self._fetch_incremental(since, limit)

        return self._fetch_with_cache(limit)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_direct(self, limit: int) -> ArticleListResult:
        """Direct FMP call; no cache interaction."""
        try:
            raw = self._fmp.get_fmp_articles(page=0, limit=limit)
        except (httpx.HTTPError, httpx.HTTPStatusError) as exc:
            raise APIError(
                "EXTERNAL_API_ERROR",
                f"FMP articles upstream failed: {exc}",
                502,
            ) from exc
        articles = [_to_article(r) for r in raw if isinstance(r, dict)]
        return ArticleListResult(
            articles=articles,
            meta=NewsListResponseMeta(cache_hit=False, fmp_calls=1, truncated=False),
        )

    def _fetch_with_cache(self, limit: int) -> ArticleListResult:
        """calendar-1d strategy: cache-first, FMP supplement on coverage miss."""
        today = date.today()
        yesterday = today - timedelta(days=1)
        as_of_dates = [today, yesterday]

        cached = cache_repo.get_cached(self._db, as_of_dates, since=None, limit=limit)

        # Coverage check: must have at least `limit` rows in cache.
        # Previously also short-circuited on "oldest cached row reaches window
        # boundary" but that branch fires for stale single-row caches and
        # prevents FMP from ever being called — observed in prod as
        # "news stuck 2 days behind even after refresh".
        coverage_ok = len(cached) >= limit

        if coverage_ok:
            return ArticleListResult(
                articles=cached[:limit],
                meta=NewsListResponseMeta(cache_hit=True, fmp_calls=0, truncated=False),
            )

        # Need to supplement from FMP
        try:
            raw = self._fmp.get_fmp_articles(page=0, limit=limit)
        except (httpx.HTTPError, httpx.HTTPStatusError) as exc:
            if cached:
                logger.warning("FMP failed, returning degraded cache: %s", exc)
                return ArticleListResult(
                    articles=cached[:limit],
                    meta=NewsListResponseMeta(
                        cache_hit=True, fmp_calls=0, truncated=False, fmp_error=True
                    ),
                )
            raise APIError(
                "EXTERNAL_API_ERROR",
                f"FMP articles upstream failed: {exc}",
                502,
            ) from exc

        articles = [_to_article(r) for r in raw if isinstance(r, dict)]
        cache_repo.upsert_many(self._db, articles, as_of=today)

        # Re-read from cache after upsert to get canonical order
        refreshed = cache_repo.get_cached(self._db, as_of_dates, since=None, limit=limit)
        return ArticleListResult(
            articles=refreshed[:limit],
            meta=NewsListResponseMeta(cache_hit=False, fmp_calls=1, truncated=False),
        )

    def _fetch_incremental(self, since: datetime, limit: int) -> ArticleListResult:
        """since-mode: paginate FMP, upsert new articles, return only newer than since."""
        today = date.today()
        new_articles: list[NewsArticle] = []
        truncated = False
        fmp_calls = 0

        for page in range(FMP_INCREMENTAL_MAX_PAGES):
            try:
                raw = self._fmp.get_fmp_articles(page=page, limit=limit)
                fmp_calls += 1
            except (httpx.HTTPError, httpx.HTTPStatusError) as exc:
                if new_articles:
                    logger.warning("FMP page %d failed, returning partial: %s", page, exc)
                    break
                raise APIError(
                    "EXTERNAL_API_ERROR",
                    f"FMP articles upstream failed: {exc}",
                    502,
                ) from exc

            if not raw:
                break

            stop = False
            for row in raw:
                if not isinstance(row, dict):
                    continue
                row_dt = _fmp_date_to_naive_utc(row.get("date"))
                if row_dt is not None and row_dt <= since:
                    stop = True
                    break
                article = _to_article(row)
                new_articles.append(article)

            if stop:
                break

            if page == FMP_INCREMENTAL_MAX_PAGES - 1:
                truncated = True
                logger.warning(
                    "Incremental fetch hit %d-page cap; truncated=true",
                    FMP_INCREMENTAL_MAX_PAGES,
                )

        cache_repo.upsert_many(self._db, new_articles, as_of=today)
        return ArticleListResult(
            articles=new_articles,
            meta=NewsListResponseMeta(
                cache_hit=False, fmp_calls=fmp_calls, truncated=truncated
            ),
        )
