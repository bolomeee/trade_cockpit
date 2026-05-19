"""F218-d4 tests — T3 NEW_PRODUCT detector (repo method + detector unit tests + end-to-end).

10 tests grouped into 3 classes:
  TestNewsCacheGetRecentForTicker — N1–N3  (repo method unit tests)
  TestDetectNewProduct            — N4–N9  (detector unit tests; N6-sub/N11 embedded in N5/N4)
  TestNewProductEndToEnd          — N10   (compute_and_store_all_triggers integration)
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Stock
from app.models.news_article_cache import NewsArticleCache
from app.models.repricing_trigger import RepricingTrigger
from app.repositories.news_cache_repository import get_recent_for_ticker
from app.services.cockpit.repricing_trigger_service import RepricingTriggerService


# ── Helpers ───────────────────────────────────────────────────────────────────

_SCAN_DATE = date(2026, 5, 1)


def _stock(db: Session, ticker: str = "NVDA") -> Stock:
    row = Stock(
        ticker=ticker,
        name=f"{ticker} Inc",
        exchange="NASDAQ",
        is_active=True,
        added_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _news(
    db: Session,
    *,
    ticker: str,
    title: str,
    url: str | None,
    published_at: datetime,
    symbols: list[str] | None = None,
    as_of_date: date,
) -> NewsArticleCache:
    if symbols is None:
        symbols = [ticker]
    payload = json.dumps({
        "title": title,
        "published_at": published_at.strftime("%Y-%m-%dT%H:%M:%S"),
        "content_html": "",
        "symbols": symbols,
        "image_url": None,
        "url": url,
        "author": None,
        "site": "test",
    })
    if url:
        article_key = url[:512]
    else:
        raw = f"{title}|{published_at.strftime('%Y-%m-%dT%H:%M:%S')}"
        article_key = hashlib.sha256(raw.encode()).hexdigest()
    row = NewsArticleCache(
        article_key=article_key,
        published_at=published_at.replace(tzinfo=None),
        as_of_date=as_of_date,
        payload_json=payload,
        cached_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(row)
    db.commit()
    return row


# ── TestNewsCacheGetRecentForTicker ───────────────────────────────────────────

class TestNewsCacheGetRecentForTicker:

    def test_n1_happy_in_window_symbols_match_desc_order(self, db_session: Session) -> None:
        """N1: articles in [scan_date-30, scan_date] with ticker in symbols returned DESC by published_at."""
        scan = _SCAN_DATE  # 2026-05-01; window = [2026-04-01, 2026-05-01]
        _news(db_session, ticker="NVDA", title="t1", url="http://u1.com",
              published_at=datetime(2026, 5, 1, 10), as_of_date=scan)
        _news(db_session, ticker="NVDA", title="t2", url="http://u2.com",
              published_at=datetime(2026, 4, 15, 10), as_of_date=date(2026, 4, 15))
        _news(db_session, ticker="NVDA", title="t3", url="http://u3.com",
              published_at=datetime(2026, 4, 1, 10), as_of_date=date(2026, 4, 1))  # lower boundary
        # Out-of-window: as_of_date < start
        _news(db_session, ticker="NVDA", title="t4", url="http://u4.com",
              published_at=datetime(2026, 3, 31, 10), as_of_date=date(2026, 3, 31))
        # In-window but symbols doesn't contain NVDA
        _news(db_session, ticker="NVDA", title="t5", url="http://u5.com",
              published_at=datetime(2026, 4, 20, 10), as_of_date=date(2026, 4, 20),
              symbols=["AAPL"])

        result = get_recent_for_ticker(db_session, "NVDA", scan_date=scan, lookback_days=30)

        assert len(result) == 3
        assert [a.url for a in result] == ["http://u1.com", "http://u2.com", "http://u3.com"]

    def test_n2_symbols_case_normalization(self, db_session: Session) -> None:
        """N2: symbols=["nvda"] + ticker="NVDA" matches; symbols=["AAPL"] + ticker="NVDA" does not."""
        scan = _SCAN_DATE
        _news(db_session, ticker="NVDA", title="lowercase symbol",
              url="http://lower.com",
              published_at=datetime(2026, 4, 20, 10), as_of_date=date(2026, 4, 20),
              symbols=["nvda"])
        _news(db_session, ticker="NVDA", title="wrong ticker",
              url="http://wrong.com",
              published_at=datetime(2026, 4, 20, 11), as_of_date=date(2026, 4, 20),
              symbols=["AAPL"])

        result = get_recent_for_ticker(db_session, "NVDA", scan_date=scan, lookback_days=30)

        assert len(result) == 1
        assert result[0].url == "http://lower.com"

    def test_n3_strict_time_boundary(self, db_session: Session) -> None:
        """N3: scan_date-30 (lower boundary) inclusive; scan_date-31 excluded; scan_date inclusive."""
        scan = _SCAN_DATE          # 2026-05-01
        lower_boundary = date(2026, 4, 1)   # scan - 30, inclusive
        outside_lower  = date(2026, 3, 31)  # scan - 31, excluded

        _news(db_session, ticker="NVDA", title="on boundary low",
              url="http://bl.com",
              published_at=datetime(2026, 4, 1, 12), as_of_date=lower_boundary)
        _news(db_session, ticker="NVDA", title="outside lower",
              url="http://ol.com",
              published_at=datetime(2026, 3, 31, 12), as_of_date=outside_lower)
        _news(db_session, ticker="NVDA", title="on scan date",
              url="http://bh.com",
              published_at=datetime(2026, 5, 1, 12), as_of_date=scan)

        result = get_recent_for_ticker(db_session, "NVDA", scan_date=scan, lookback_days=30)

        urls = {a.url for a in result}
        assert "http://bl.com" in urls   # lower boundary → included
        assert "http://bh.com" in urls   # upper boundary → included
        assert "http://ol.com" not in urls  # outside lower → excluded


# ── TestDetectNewProduct ──────────────────────────────────────────────────────

class TestDetectNewProduct:

    def _svc(self, db: Session) -> RepricingTriggerService:
        return RepricingTriggerService(db)

    def test_n4_happy_multi_article_multi_keyword(self, db_session: Session) -> None:
        """N4: 2 articles, AI×2 + launch×1 = 3 total hits → trigger; schema correct. (N11 embedded: count DESC sort)"""
        scan = _SCAN_DATE
        _stock(db_session, "NVDA")
        _news(db_session, ticker="NVDA", title="AI launch event",
              url="http://a1.com",
              published_at=datetime(2026, 4, 20, 15), as_of_date=date(2026, 4, 20))
        _news(db_session, ticker="NVDA", title="AI rollout recap",
              url="http://a2.com",
              published_at=datetime(2026, 4, 18, 10), as_of_date=date(2026, 4, 18))

        result = self._svc(db_session)._detect_new_product("NVDA", scan)

        assert result is not None
        assert result.confidence == 0.5
        ev = result.evidence
        assert ev["scan_window_days"] == 30
        # news_links ordered published_at DESC: a1 (apr 20) before a2 (apr 18)
        assert ev["news_links"] == ["http://a1.com", "http://a2.com"]
        # N11 embedded: keyword_hits sorted count DESC; AI=2 must precede launch=1
        hits = {h["keyword"]: h["count"] for h in ev["keyword_hits"]}
        assert hits["AI"] == 2
        assert hits["launch"] == 1
        assert ev["keyword_hits"][0]["keyword"] == "AI"
        assert ev["keyword_hits"][0]["count"] == 2

    def test_n5_single_article_multi_keyword_and_same_kw_counts_once(self, db_session: Session) -> None:
        """N5: 1 article "unveils new platform with AI" → 3 hits → trigger.
        N6-sub embedded: title="AI AI AI day" → keyword AI count=1, not 3."""
        scan = _SCAN_DATE
        _stock(db_session, "NVDA")
        _news(db_session, ticker="NVDA",
              title="NVDA unveils new platform with AI",
              url="http://n5.com",
              published_at=datetime(2026, 4, 25, 10), as_of_date=date(2026, 4, 25))

        result = self._svc(db_session)._detect_new_product("NVDA", scan)

        assert result is not None
        hits = {h["keyword"]: h["count"] for h in result.evidence["keyword_hits"]}
        assert "unveil" in hits      # "unveil" is substring of "unveils"
        assert "AI" in hits
        assert "platform" in hits
        assert sum(hits.values()) >= 2

        # N6-sub: "AI AI AI day" title → keyword "AI" counts as 1 (not 3)
        db_session.query(NewsArticleCache).delete()
        db_session.commit()
        _news(db_session, ticker="NVDA", title="AI AI AI day",
              url="http://rep1.com",
              published_at=datetime(2026, 4, 22, 10), as_of_date=date(2026, 4, 22))
        _news(db_session, ticker="NVDA", title="launch event recap",
              url="http://rep2.com",
              published_at=datetime(2026, 4, 21, 10), as_of_date=date(2026, 4, 21))

        result2 = self._svc(db_session)._detect_new_product("NVDA", scan)
        assert result2 is not None
        hits2 = {h["keyword"]: h["count"] for h in result2.evidence["keyword_hits"]}
        assert hits2.get("AI") == 1  # "AI AI AI" in one title → count=1, not 3

    def test_n6_total_hits_below_threshold_returns_none(self, db_session: Session) -> None:
        """N6: only "launch" in 1 article → total_hits=1 < T3_MIN_TOTAL_HITS=2 → None."""
        scan = _SCAN_DATE
        _stock(db_session, "NVDA")
        _news(db_session, ticker="NVDA", title="quarterly launch report",
              url="http://n6.com",
              published_at=datetime(2026, 4, 20, 10), as_of_date=date(2026, 4, 20))

        result = self._svc(db_session)._detect_new_product("NVDA", scan)
        assert result is None

    def test_n7_no_matching_news_returns_none(self, db_session: Session) -> None:
        """N7: ticker has no matching news in 30-day window → None without error."""
        scan = _SCAN_DATE
        _stock(db_session, "NVDA")
        # Only AAPL article, not NVDA
        _news(db_session, ticker="AAPL", title="AI platform launch",
              url="http://n7.com",
              published_at=datetime(2026, 4, 20, 10), as_of_date=date(2026, 4, 20),
              symbols=["AAPL"])

        result = self._svc(db_session)._detect_new_product("NVDA", scan)
        assert result is None

    def test_n8_news_links_capped_at_five(self, db_session: Session) -> None:
        """N8: 7 hit articles → news_links at most 5, newest first (published_at DESC)."""
        scan = _SCAN_DATE
        _stock(db_session, "NVDA")
        for i in range(7):
            _news(db_session, ticker="NVDA",
                  title=f"AI product launch article {i}",
                  url=f"http://n8-{i}.com",
                  published_at=datetime(2026, 4, 10 + i, 10),
                  as_of_date=date(2026, 4, 10 + i))

        result = self._svc(db_session)._detect_new_product("NVDA", scan)

        assert result is not None
        assert len(result.evidence["news_links"]) == 5
        # Newest article is i=6 (published_at apr 16) → appears first
        assert result.evidence["news_links"][0] == "http://n8-6.com"

    def test_n9_url_dedup_and_null_url_tolerance(self, db_session: Session) -> None:
        """N9: 3 hit articles, 1 url=None → news_links has 2 URLs, no None, no AttributeError."""
        scan = _SCAN_DATE
        _stock(db_session, "NVDA")
        _news(db_session, ticker="NVDA", title="AI platform day1",
              url="http://n9a.com",
              published_at=datetime(2026, 4, 22, 10), as_of_date=date(2026, 4, 22))
        _news(db_session, ticker="NVDA", title="AI platform day2",
              url=None,
              published_at=datetime(2026, 4, 21, 10), as_of_date=date(2026, 4, 21))
        _news(db_session, ticker="NVDA", title="AI platform day3",
              url="http://n9b.com",
              published_at=datetime(2026, 4, 20, 10), as_of_date=date(2026, 4, 20))

        result = self._svc(db_session)._detect_new_product("NVDA", scan)

        assert result is not None
        links = result.evidence["news_links"]
        assert None not in links
        assert len(links) == 2
        assert "http://n9a.com" in links
        assert "http://n9b.com" in links


# ── TestNewProductEndToEnd ────────────────────────────────────────────────────

class TestNewProductEndToEnd:

    def test_n10_hit_upserts_then_expire_on_empty_news(self, db_session: Session) -> None:
        """N10: 4 hit news → NEW_PRODUCT active=True + evidence_json 3 keys; clear news → active=False."""
        scan = _SCAN_DATE
        _stock(db_session, "NVDA")
        for i in range(4):
            _news(db_session, ticker="NVDA",
                  title=f"NVDA AI platform launch {i}",
                  url=f"http://n10-{i}.com",
                  published_at=datetime(2026, 4, 10 + i, 10),
                  as_of_date=date(2026, 4, 10 + i))

        svc = RepricingTriggerService(db_session)
        svc.compute_and_store_all_triggers(scan)

        row = db_session.execute(
            select(RepricingTrigger).where(
                RepricingTrigger.ticker == "NVDA",
                RepricingTrigger.trigger_type == "NEW_PRODUCT",
            )
        ).scalar_one()
        assert row.active is True
        ev = json.loads(row.evidence_json)
        assert "keyword_hits" in ev
        assert "news_links" in ev
        assert ev["scan_window_days"] == 30

        # Delete news → soft expire (next day scan so detected_date < current_date)
        db_session.query(NewsArticleCache).delete()
        db_session.commit()
        svc.compute_and_store_all_triggers(scan + timedelta(days=1))
        db_session.expire_all()

        row_after = db_session.execute(
            select(RepricingTrigger).where(
                RepricingTrigger.ticker == "NVDA",
                RepricingTrigger.trigger_type == "NEW_PRODUCT",
            )
        ).scalar_one()
        assert row_after.active is False
