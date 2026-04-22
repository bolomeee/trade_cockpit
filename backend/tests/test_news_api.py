"""F112-a: news API + service unit tests.

Covers:
- `FmpClient.get_fmp_articles` path + param passthrough
- `NewsService` field normalization (date, tickers) with edge cases
- `GET /api/news/articles` happy path, empty, validation, upstream failure
"""
from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.external.fmp_client import FMP_EP_FMP_ARTICLES, FmpClient, _FmpRateLimiter
from app.main import app
from app.routers.news import get_news_service
from app.services.news_service import (
    NewsService,
    normalize_tickers,
    to_iso_datetime,
)


# --- FmpClient.get_fmp_articles -----------------------------------------


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
    # Fresh limiter so rate state does not leak across tests.
    limiter = _FmpRateLimiter(time_source=lambda: 1000.0, sleep=lambda _s: None)
    client = FmpClient(api_key=api_key, _http_client=http, rate_limiter=limiter)
    return client, captured


def test_get_fmp_articles_passes_params():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"title": "t"}])

    client, captured = _make_client(handler)
    out = client.get_fmp_articles(page=0, limit=5)

    assert out == [{"title": "t"}]
    assert len(captured) == 1
    req = captured[0]
    assert req.url.path.endswith(FMP_EP_FMP_ARTICLES)
    params = dict(req.url.params)
    assert params["page"] == "0"
    assert params["limit"] == "5"
    assert params["apikey"] == "test-key"


def test_get_fmp_articles_returns_raw_list_unchanged():
    raw = [
        {"title": "A", "date": "2026-04-21 21:11:13", "tickers": "NASDAQ:CYTK"},
        {"title": "B"},
    ]

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=raw)

    client, _ = _make_client(handler)
    assert client.get_fmp_articles() == raw


def test_get_fmp_articles_empty_body():
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    client, _ = _make_client(handler)
    assert client.get_fmp_articles() == []


# --- normalize_tickers -------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("NASDAQ:CYTK, NYSE:CB", ["CYTK", "CB"]),
        ("CYTK", ["CYTK"]),
        ("", []),
        (None, []),
        ("NASDAQ:CYTK, NYSE:CYTK", ["CYTK"]),  # de-dup preserve order
        ("  NASDAQ:AAPL ,  NYSE:MSFT  ", ["AAPL", "MSFT"]),
        ("NASDAQ:, NYSE:CB", ["CB"]),  # empty symbol part dropped
    ],
)
def test_normalize_tickers(raw, expected):
    assert normalize_tickers(raw) == expected


# --- to_iso_datetime ---------------------------------------------------


def test_to_iso_datetime_fmp_format():
    assert to_iso_datetime("2026-04-21 21:11:13") == "2026-04-21T21:11:13Z"


def test_to_iso_datetime_invalid_preserved():
    # Bad row should not taint the list — return the original string.
    assert to_iso_datetime("not-a-date") == "not-a-date"


def test_to_iso_datetime_empty():
    assert to_iso_datetime("") == ""
    assert to_iso_datetime(None) == ""


# --- NewsService -------------------------------------------------------


class _FakeFMPArticles:
    def __init__(self) -> None:
        self.result: list[Any] = []
        self.calls: list[tuple[int, int]] = []
        self.exc: Exception | None = None

    def get_fmp_articles(self, page: int = 0, limit: int = 20) -> list[dict[str, Any]]:
        self.calls.append((page, limit))
        if self.exc is not None:
            raise self.exc
        return list(self.result)


def test_news_service_normalizes_all_fields():
    fake = _FakeFMPArticles()
    fake.result = [
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
    ]
    svc = NewsService(fake)  # type: ignore[arg-type]
    [article] = svc.list_articles(limit=10)

    assert article.title == "Headline"
    assert article.published_at == "2026-04-21T21:11:13Z"
    assert article.content_html == "<p>body</p>"
    assert article.symbols == ["CYTK", "CB"]
    assert article.image_url == "https://img/1.jpg"
    assert article.url == "https://site/a"
    assert article.author == "Jane"
    assert article.site == "FMP"
    assert fake.calls == [(0, 10)]


def test_news_service_empty_tickers_yields_empty_symbols():
    fake = _FakeFMPArticles()
    fake.result = [{"title": "x", "date": "2026-04-21 00:00:00"}]
    svc = NewsService(fake)  # type: ignore[arg-type]
    [article] = svc.list_articles()
    assert article.symbols == []


def test_news_service_upstream_error_maps_to_api_error():
    from app.services.watchlist_service import APIError

    fake = _FakeFMPArticles()
    fake.exc = httpx.ConnectError("boom")
    svc = NewsService(fake)  # type: ignore[arg-type]
    with pytest.raises(APIError) as ei:
        svc.list_articles()
    assert ei.value.code == "EXTERNAL_API_ERROR"
    assert ei.value.status_code == 502


# --- integration: GET /api/news/articles -------------------------------


def _override_news_service(client, fake: _FakeFMPArticles) -> None:
    app.dependency_overrides[get_news_service] = lambda: NewsService(fake)  # type: ignore[arg-type]


def _clear_news_override() -> None:
    app.dependency_overrides.pop(get_news_service, None)


def test_news_api_happy_path(client):
    fake = _FakeFMPArticles()
    fake.result = [
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
    ]
    _override_news_service(client, fake)
    try:
        resp = client.get("/api/news/articles?limit=5")
    finally:
        _clear_news_override()

    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] == "success"
    assert len(body["data"]) == 1
    item = body["data"][0]
    assert item == {
        "title": "A",
        "publishedAt": "2026-04-21T10:00:00Z",
        "contentHtml": "<p>c</p>",
        "symbols": ["AAPL"],
        "imageUrl": "i",
        "url": "u",
        "author": "x",
        "site": "s",
    }
    assert fake.calls == [(0, 5)]


def test_news_api_empty_list(client):
    fake = _FakeFMPArticles()
    fake.result = []
    _override_news_service(client, fake)
    try:
        resp = client.get("/api/news/articles")
    finally:
        _clear_news_override()

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []


def test_news_api_default_limit_20(client):
    fake = _FakeFMPArticles()
    _override_news_service(client, fake)
    try:
        resp = client.get("/api/news/articles")
    finally:
        _clear_news_override()

    assert resp.status_code == 200
    assert fake.calls == [(0, 20)]


@pytest.mark.parametrize("limit", [0, 51, 100, -1])
def test_news_api_rejects_out_of_range_limit(client, limit):
    fake = _FakeFMPArticles()
    _override_news_service(client, fake)
    try:
        resp = client.get(f"/api/news/articles?limit={limit}")
    finally:
        _clear_news_override()
    assert resp.status_code == 422
    assert fake.calls == []  # service never invoked


def test_news_api_upstream_failure_502(client):
    fake = _FakeFMPArticles()
    fake.exc = httpx.ConnectError("net down")
    _override_news_service(client, fake)
    try:
        resp = client.get("/api/news/articles")
    finally:
        _clear_news_override()

    assert resp.status_code == 502
    body = resp.json()
    assert body["error"]["code"] == "EXTERNAL_API_ERROR"
