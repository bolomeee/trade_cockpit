"""News API + service unit/integration tests (F112-a + F113-a).

Covers (F112-a, preserved):
- FmpClient.get_fmp_articles param passthrough
- NewsService field normalization
- GET /api/news/articles happy path, empty, upstream failure

Covers (F113-a, new):
- MAX_LIMIT raised to 200
- ?since= incremental mode (stop at page with old article, truncated=true)
- ?window=calendar-1d cache-first path
- ?window=none skip-cache path
- FMP failure + cache populated → degraded 200
- FMP failure + cache empty → 502
- Invalid since → 422
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from app.external.fmp_client import FMP_EP_FMP_ARTICLES, FmpClient, _FmpRateLimiter
from app.main import app
from app.repositories import news_cache_repository as cache_repo
from app.routers.news import get_news_service
from app.schemas.news import NewsArticle
from app.services.news_service import (
    ArticleListResult,
    NewsService,
    _to_article,
    extract_exchange_prefixed_tickers,
    normalize_tickers,
    to_iso_datetime,
)


# ---------------------------------------------------------------------------
# FmpClient transport helpers
# ---------------------------------------------------------------------------


def _make_client(handler, api_key="test-key"):
    captured: list[httpx.Request] = []

    def wrapped(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return handler(req)

    transport = httpx.MockTransport(wrapped)
    http = httpx.Client(
        base_url="https://financialmodelingprep.com/stable",
        transport=transport,
    )
    limiter = _FmpRateLimiter(time_source=lambda: 1000.0, sleep=lambda _s: None)
    return FmpClient(api_key=api_key, _http_client=http, rate_limiter=limiter), captured


def test_get_fmp_articles_passes_params():
    def handler(_req):
        return httpx.Response(200, json=[{"title": "t"}])

    client, captured = _make_client(handler)
    out = client.get_fmp_articles(page=0, limit=5)

    assert out == [{"title": "t"}]
    assert len(captured) == 1
    params = dict(captured[0].url.params)
    assert params["page"] == "0"
    assert params["limit"] == "5"
    assert params["apikey"] == "test-key"


def test_get_fmp_articles_returns_raw_list_unchanged():
    raw = [{"title": "A", "date": "2026-04-21 21:11:13", "tickers": "NASDAQ:CYTK"}]

    def handler(_req):
        return httpx.Response(200, json=raw)

    client, _ = _make_client(handler)
    assert client.get_fmp_articles() == raw


def test_get_fmp_articles_empty_body():
    def handler(_req):
        return httpx.Response(200, json=[])

    client, _ = _make_client(handler)
    assert client.get_fmp_articles() == []


# ---------------------------------------------------------------------------
# normalize_tickers / to_iso_datetime
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("NASDAQ:CYTK, NYSE:CB", ["CYTK", "CB"]),
        ("CYTK", ["CYTK"]),
        ("", []),
        (None, []),
        ("NASDAQ:CYTK, NYSE:CYTK", ["CYTK"]),
        ("  NASDAQ:AAPL ,  NYSE:MSFT  ", ["AAPL", "MSFT"]),
        ("NASDAQ:, NYSE:CB", ["CB"]),
    ],
)
def test_normalize_tickers(raw, expected):
    assert normalize_tickers(raw) == expected


def test_to_iso_datetime_fmp_format():
    assert to_iso_datetime("2026-04-21 21:11:13") == "2026-04-21T21:11:13Z"


def test_to_iso_datetime_invalid_preserved():
    assert to_iso_datetime("not-a-date") == "not-a-date"


def test_to_iso_datetime_empty():
    assert to_iso_datetime("") == ""


# ---------------------------------------------------------------------------
# extract_exchange_prefixed_tickers / _to_article merge
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Axe Compute (NASDAQ: AGPU) surged", ["AGPU"]),
        ("Toro Corp (NYSE:TORO) announced", ["TORO"]),
        ("(nasdaq: AGPU)", ["AGPU"]),
        ("(NASDAQ: agpu)", []),
        ("Akanda (AKAN) gained", []),
        ("CEO Tim Cook (CEO) said", []),
        ("(NASDAQ: AGPU) and (NYSE: TORO) and (NYSE:TORO)", ["AGPU", "TORO"]),
        ("(NYSEARCA: SPY) and (OTCQB: XYZ) and (AMEX: ABC)", ["SPY", "XYZ", "ABC"]),
        ("", []),
        (None, []),
    ],
)
def test_extract_exchange_prefixed_tickers(text, expected):
    assert extract_exchange_prefixed_tickers(text) == expected


def test_to_article_merges_fmp_tickers_with_title_extraction():
    row = {
        "title": "Movers: Axe (NASDAQ: AGPU), Toro (NYSE: TORO)",
        "content": "Details about (NASDAQ: AGPU).",
        "tickers": "NASDAQ:CYTK",
        "date": "2026-04-23 10:00:00",
        "link": "https://example.com/a",
    }
    article = _to_article(row)
    assert article.symbols == ["CYTK", "AGPU", "TORO"]


def test_to_article_without_exchange_prefix_keeps_fmp_only():
    row = {
        "title": "Top Movers: Akanda (AKAN), Toro (TORO)",
        "content": "",
        "tickers": "NASDAQ:AKAN",
        "date": "2026-04-23 10:00:00",
    }
    article = _to_article(row)
    assert article.symbols == ["AKAN"]
    assert to_iso_datetime(None) == ""


# ---------------------------------------------------------------------------
# NewsService — fake FMP helper
# ---------------------------------------------------------------------------


class _FakeFMP:
    """Per-page programmable stub for FmpClient.get_fmp_articles."""

    def __init__(self, pages: dict[int, list[dict]] | None = None) -> None:
        # pages: {page_number: list_of_rows} — missing pages return []
        self._pages: dict[int, list[dict]] = pages or {}
        self.calls: list[tuple[int, int]] = []
        self.exc: Exception | None = None

    def get_fmp_articles(self, page: int = 0, limit: int = 20) -> list[dict[str, Any]]:
        self.calls.append((page, limit))
        if self.exc is not None:
            raise self.exc
        return list(self._pages.get(page, []))


def _row(
    title: str = "T",
    date_str: str = "2026-04-22 10:00:00",
    link: str | None = None,
) -> dict:
    return {
        "title": title,
        "date": date_str,
        "content": "<p>body</p>",
        "tickers": "NASDAQ:AAPL",
        "link": link or f"https://site.com/{title}",
    }


# ---------------------------------------------------------------------------
# NewsService unit tests
# ---------------------------------------------------------------------------


def test_news_service_normalizes_all_fields():
    fake = _FakeFMP(pages={0: [
        {
            "title": "Headline",
            "date": "2026-04-21 21:11:13",
            "content": "<p>body</p>",
            "tickers": "NASDAQ:CYTK, NYSE:CB",
            "image": "https://img/1.jpg",
            "link": "https://site/a",
            "author": "Jane",
            "site": "FMP",
        }
    ]})
    svc = NewsService(fake)  # type: ignore[arg-type]
    result = svc.list_articles(limit=10, window="none")
    [article] = result.articles

    assert article.title == "Headline"
    assert article.published_at == "2026-04-21T21:11:13Z"
    assert article.symbols == ["CYTK", "CB"]
    assert fake.calls == [(0, 10)]


def test_news_service_upstream_error_maps_to_api_error():
    from app.services.watchlist_service import APIError

    fake = _FakeFMP()
    fake.exc = httpx.ConnectError("boom")
    svc = NewsService(fake)  # type: ignore[arg-type]
    with pytest.raises(APIError) as ei:
        svc.list_articles(window="none")
    assert ei.value.code == "EXTERNAL_API_ERROR"
    assert ei.value.status_code == 502


# F113-a: incremental since-mode stops when FMP row date <= since

def test_incremental_stops_at_old_article(db_session):
    since = datetime(2026, 4, 21, 12, 0, 0)
    pages = {
        0: [_row("new1", "2026-04-22 10:00:00", "https://a.com/1"), _row("new2", "2026-04-22 09:00:00", "https://a.com/2")],
        1: [_row("new3", "2026-04-22 08:00:00", "https://a.com/3"), _row("old", "2026-04-21 11:00:00", "https://a.com/old")],
    }
    fake = _FakeFMP(pages=pages)
    svc = NewsService(fake, db=db_session)  # type: ignore[arg-type]
    result = svc.list_articles(limit=20, since=since)

    assert len(result.articles) == 3
    titles = [a.title for a in result.articles]
    assert "old" not in titles
    assert result.meta.fmp_calls == 2
    assert result.meta.truncated is False


def test_incremental_truncated_at_max_pages(db_session):
    from app.services.news_service import FMP_INCREMENTAL_MAX_PAGES

    since = datetime(2026, 4, 1, 0, 0, 0)
    pages = {
        i: [_row(f"art{i}", "2026-04-22 10:00:00", f"https://a.com/{i}")]
        for i in range(FMP_INCREMENTAL_MAX_PAGES)
    }
    fake = _FakeFMP(pages=pages)
    svc = NewsService(fake, db=db_session)  # type: ignore[arg-type]
    result = svc.list_articles(limit=20, since=since)

    assert result.meta.truncated is True
    assert result.meta.fmp_calls == FMP_INCREMENTAL_MAX_PAGES


def test_window_none_skips_cache(db_session):
    """window=none must call FMP even when db session is present."""
    fake = _FakeFMP(pages={0: [_row("A")]})
    svc = NewsService(fake, db=db_session)  # type: ignore[arg-type]
    result = svc.list_articles(limit=20, window="none")
    assert fake.calls == [(0, 20)]
    assert result.meta.cache_hit is False


def test_cache_hit_no_fmp_call(db_session):
    """Second calendar-1d call should hit cache without touching FMP."""
    today = date.today()
    articles = [
        NewsArticle(
            title=str(i),
            published_at=f"2026-04-22T{10+i:02d}:00:00Z",
            content_html="",
            symbols=[],
            url=f"https://a.com/{i}",
        )
        for i in range(5)
    ]
    cache_repo.upsert_many(db_session, articles, as_of=today)

    fake = _FakeFMP()
    svc = NewsService(fake, db=db_session)  # type: ignore[arg-type]
    result = svc.list_articles(limit=5, window="calendar-1d")

    assert fake.calls == []
    assert result.meta.cache_hit is True
    assert result.meta.fmp_calls == 0


def test_fmp_failure_with_cached_data_returns_degraded(db_session):
    """FMP error + cache populated → 200 degraded response."""
    from app.services.watchlist_service import APIError

    today = date.today()
    cache_repo.upsert_many(
        db_session,
        [NewsArticle(title="cached", published_at="2026-04-22T10:00:00Z", content_html="", symbols=[], url="https://a.com/c")],
        as_of=today,
    )
    fake = _FakeFMP()
    fake.exc = httpx.ConnectError("down")
    svc = NewsService(fake, db=db_session)  # type: ignore[arg-type]

    result = svc.list_articles(limit=5, window="calendar-1d")
    assert result.articles[0].title == "cached"
    assert result.meta.cache_hit is True
    assert result.meta.fmp_error is True


def test_fmp_failure_with_empty_cache_raises(db_session):
    from app.services.watchlist_service import APIError

    fake = _FakeFMP()
    fake.exc = httpx.ConnectError("down")
    svc = NewsService(fake, db=db_session)  # type: ignore[arg-type]

    with pytest.raises(APIError) as ei:
        svc.list_articles(limit=5, window="calendar-1d")
    assert ei.value.status_code == 502


# ---------------------------------------------------------------------------
# Integration: GET /api/news/articles via HTTP
# ---------------------------------------------------------------------------


def _override_news_service(client, fake: _FakeFMP, db=None) -> None:
    from app.services.news_service import NewsService as _NS
    app.dependency_overrides[get_news_service] = lambda: _NS(fake, db)  # type: ignore[arg-type]


def _clear_override():
    app.dependency_overrides.pop(get_news_service, None)


def test_news_api_happy_path(client):
    fake = _FakeFMP(pages={0: [
        {
            "title": "A",
            "date": "2026-04-21 10:00:00",
            "content": "<p>c</p>",
            "tickers": "NASDAQ:AAPL",
            "image": "i",
            "link": "u",
            "author": "x",
            "site": "s",
        }
    ]})
    _override_news_service(client, fake)
    try:
        resp = client.get("/api/news/articles?limit=5&window=none")
    finally:
        _clear_override()

    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] == "success"
    assert len(body["data"]) == 1
    item = body["data"][0]
    assert item["title"] == "A"
    assert item["publishedAt"] == "2026-04-21T10:00:00Z"
    assert item["symbols"] == ["AAPL"]
    assert "meta" in body


def test_news_api_empty_list(client):
    fake = _FakeFMP(pages={0: []})
    _override_news_service(client, fake)
    try:
        resp = client.get("/api/news/articles?window=none")
    finally:
        _clear_override()
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_news_api_default_limit_20(client):
    fake = _FakeFMP(pages={0: []})
    _override_news_service(client, fake)
    try:
        resp = client.get("/api/news/articles?window=none")
    finally:
        _clear_override()
    assert resp.status_code == 200
    assert fake.calls == [(0, 20)]


@pytest.mark.parametrize("limit", [0, -1, 201])
def test_news_api_rejects_out_of_range_limit(client, limit):
    fake = _FakeFMP()
    _override_news_service(client, fake)
    try:
        resp = client.get(f"/api/news/articles?limit={limit}")
    finally:
        _clear_override()
    assert resp.status_code == 422
    assert fake.calls == []


@pytest.mark.parametrize("limit", [1, 51, 100, 200])
def test_news_api_accepts_limit_up_to_200(client, limit):
    fake = _FakeFMP(pages={0: []})
    _override_news_service(client, fake)
    try:
        resp = client.get(f"/api/news/articles?limit={limit}&window=none")
    finally:
        _clear_override()
    assert resp.status_code == 200


def test_news_api_upstream_failure_502(client):
    fake = _FakeFMP()
    fake.exc = httpx.ConnectError("net down")
    _override_news_service(client, fake)
    try:
        resp = client.get("/api/news/articles?window=none")
    finally:
        _clear_override()
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "EXTERNAL_API_ERROR"


def test_news_api_invalid_since_returns_422(client):
    fake = _FakeFMP()
    _override_news_service(client, fake)
    try:
        resp = client.get("/api/news/articles?since=not-a-date")
    finally:
        _clear_override()
    assert resp.status_code == 422


def test_news_api_invalid_window_returns_422(client):
    fake = _FakeFMP()
    _override_news_service(client, fake)
    try:
        resp = client.get("/api/news/articles?window=invalid")
    finally:
        _clear_override()
    assert resp.status_code == 422


def test_news_api_window_none_compat_with_f112a(client):
    """window=none must preserve F112-a direct-FMP behaviour."""
    fake = _FakeFMP(pages={0: [_row("A")]})
    _override_news_service(client, fake)
    try:
        resp = client.get("/api/news/articles?window=none&limit=50")
    finally:
        _clear_override()
    assert resp.status_code == 200
    assert fake.calls == [(0, 50)]
