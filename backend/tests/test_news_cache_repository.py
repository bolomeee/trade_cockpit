"""Unit tests for news_cache_repository (F113-a).

Covers:
- compute_article_key: URL-first, hash fallback, precision truncation
- upsert_many: inserts new rows, skips duplicates
- get_cached: filtering by as_of_date, since, limit
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.repositories.news_cache_repository import (
    compute_article_key,
    get_cached,
    upsert_many,
)
from app.schemas.news import NewsArticle


def _article(
    title: str = "T",
    published_at: str = "2026-04-21T10:00:00Z",
    url: str | None = "https://example.com/a",
) -> NewsArticle:
    return NewsArticle(
        title=title,
        published_at=published_at,
        content_html="<p>body</p>",
        symbols=["AAPL"],
        url=url,
    )


# --- compute_article_key -----------------------------------------------


def test_key_uses_url_when_present():
    a = _article(url="https://site.com/story-1")
    assert compute_article_key(a) == "https://site.com/story-1"


def test_key_truncates_url_to_512():
    long_url = "https://x.com/" + "a" * 600
    a = _article(url=long_url)
    assert len(compute_article_key(a)) == 512


def test_key_falls_back_to_hash_when_no_url():
    a = _article(url=None, title="Unique title", published_at="2026-04-21T10:00:00Z")
    key = compute_article_key(a)
    assert len(key) == 64  # SHA-256 hex
    # Same input → same key
    assert compute_article_key(a) == key


def test_key_hash_uses_second_precision():
    """Sub-second differences in published_at should not change the key."""
    a1 = _article(url=None, title="X", published_at="2026-04-21T10:00:00Z")
    a2 = _article(url=None, title="X", published_at="2026-04-21T10:00:00.999Z")
    assert compute_article_key(a1) == compute_article_key(a2)


def test_key_different_articles_give_different_hashes():
    a1 = _article(url=None, title="A", published_at="2026-04-21T10:00:00Z")
    a2 = _article(url=None, title="B", published_at="2026-04-21T10:00:00Z")
    assert compute_article_key(a1) != compute_article_key(a2)


# --- upsert_many -------------------------------------------------------


def test_upsert_inserts_new_articles(db_session):
    today = date(2026, 4, 21)
    articles = [_article(title="A"), _article(title="B", url="https://site.com/b")]
    count = upsert_many(db_session, articles, as_of=today)
    assert count == 2


def test_upsert_skips_duplicates(db_session):
    today = date(2026, 4, 21)
    a = _article(title="A")
    upsert_many(db_session, [a], as_of=today)
    count2 = upsert_many(db_session, [a], as_of=today)
    assert count2 == 0


def test_upsert_empty_list(db_session):
    assert upsert_many(db_session, [], as_of=date.today()) == 0


def test_upsert_same_key_different_date_allowed(db_session):
    a = _article()
    upsert_many(db_session, [a], as_of=date(2026, 4, 20))
    count = upsert_many(db_session, [a], as_of=date(2026, 4, 21))
    assert count == 1


# --- get_cached --------------------------------------------------------


def test_get_cached_returns_articles_for_given_dates(db_session):
    today = date(2026, 4, 21)
    a = _article(title="A", published_at="2026-04-21T10:00:00Z")
    upsert_many(db_session, [a], as_of=today)

    result = get_cached(db_session, [today], since=None, limit=10)
    assert len(result) == 1
    assert result[0].title == "A"


def test_get_cached_excludes_other_dates(db_session):
    upsert_many(db_session, [_article()], as_of=date(2026, 4, 19))
    result = get_cached(db_session, [date(2026, 4, 21)], since=None, limit=10)
    assert result == []


def test_get_cached_filters_by_since(db_session):
    today = date(2026, 4, 21)
    old = _article(title="old", published_at="2026-04-20T10:00:00Z", url="https://a.com/old")
    new = _article(title="new", published_at="2026-04-21T10:00:00Z", url="https://a.com/new")
    upsert_many(db_session, [old, new], as_of=today)

    since = datetime(2026, 4, 20, 12, 0, 0)
    result = get_cached(db_session, [today], since=since, limit=10)
    assert len(result) == 1
    assert result[0].title == "new"


def test_get_cached_respects_limit(db_session):
    today = date(2026, 4, 21)
    articles = [
        _article(
            title=str(i),
            published_at=f"2026-04-21T{10+i:02d}:00:00Z",
            url=f"https://a.com/{i}",
        )
        for i in range(5)
    ]
    upsert_many(db_session, articles, as_of=today)
    result = get_cached(db_session, [today], since=None, limit=3)
    assert len(result) == 3


def test_get_cached_orders_by_published_at_desc(db_session):
    today = date(2026, 4, 21)
    a1 = _article(title="early", published_at="2026-04-21T08:00:00Z", url="https://a.com/1")
    a2 = _article(title="late", published_at="2026-04-21T10:00:00Z", url="https://a.com/2")
    upsert_many(db_session, [a1, a2], as_of=today)
    result = get_cached(db_session, [today], since=None, limit=10)
    assert result[0].title == "late"
    assert result[1].title == "early"
