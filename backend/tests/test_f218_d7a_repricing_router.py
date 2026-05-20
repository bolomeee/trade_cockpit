"""Integration tests for F218-d7a /api/cockpit/repricing-triggers endpoints.

Sprint Contract 标准 R1–R8:
  R1. seed NVDA 2 active triggers → GET /NVDA → 200, camelCase, evidence keys camelCase
  R2. no active triggers → 200 + triggers=[]
  R3. invalid ticker → 422 + VALIDATION_ERROR
  R4. lowercase input → auto-upper, data.ticker="NVDA"
  R5. 3 tickers × 5 types (15 rows) → GET / → 200, triggers=15, totalCount=15, sorting
  R6. ?triggerType=BALANCE_INFLECTION → filter
  R7. invalid triggerType / limit → 422
  R8. empty table → 200 + [] + totalCount=0 + valid computedAt ISO8601 UTC
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.repricing_trigger import RepricingTrigger

_EVIDENCE_BY_TYPE: dict[str, dict] = {
    "EARNINGS_ACCEL":     {"eps_yoy_growth": [0.2, 0.3], "revenue_yoy_growth": [0.1, 0.15]},
    "MARGIN_EXPANSION":   {"trigger_metric": "gross_margin", "expansion_bp": 900},
    "NEW_PRODUCT":        {"match_count": 3, "keywords": ["launch", "AI"]},
    "SECTOR_CYCLE":       {"rs_percentile": 65, "sector_etf": "XLK"},
    "BALANCE_INFLECTION": {"net_debt_trend": "declining", "fcf_trend": "rising",
                           "trigger_metric": "net_debt", "quarters": 3},
}


def _seed_trigger(
    db: Session,
    *,
    ticker: str,
    trigger_type: str,
    detected_date: date = date(2026, 1, 1),
    confidence: float = 0.5,
    evidence: dict | None = None,
    active: bool = True,
    computed_at: datetime | None = None,
) -> RepricingTrigger:
    if evidence is None:
        evidence = _EVIDENCE_BY_TYPE.get(trigger_type, {"test": True})
    if computed_at is None:
        computed_at = datetime(2026, 1, 2, 22, 40, tzinfo=timezone.utc)
    row = RepricingTrigger(
        ticker=ticker,
        trigger_type=trigger_type,
        detected_date=detected_date,
        confidence=confidence,
        evidence_json=json.dumps(evidence),
        active=active,
        computed_at=computed_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ── TestTickerEndpoint ────────────────────────────────────────────────────────


class TestTickerEndpoint:
    def test_r1_returns_active_triggers_with_camelcase(self, client, db_session):
        """R1: 2 active NVDA triggers → 200, envelope, camelCase fields, evidence camelCase."""
        _seed_trigger(
            db_session, ticker="NVDA", trigger_type="MARGIN_EXPANSION",
            detected_date=date(2026, 1, 3),
            confidence=0.85,
            evidence={"trigger_metric": "gross_margin", "expansion_bp": 900},
        )
        _seed_trigger(
            db_session, ticker="NVDA", trigger_type="EARNINGS_ACCEL",
            detected_date=date(2026, 1, 1),
            confidence=0.70,
        )

        resp = client.get("/api/cockpit/repricing-triggers/NVDA")
        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "success"
        data = body["data"]
        assert data["ticker"] == "NVDA"
        triggers = data["triggers"]
        assert len(triggers) == 2
        # detectedDate DESC: 2026-01-03 first
        assert triggers[0]["detectedDate"] == "2026-01-03"
        assert triggers[1]["detectedDate"] == "2026-01-01"
        # camelCase field names
        first = triggers[0]
        assert "triggerType" in first
        assert "detectedDate" in first
        assert "computedAt" in first
        assert first["triggerType"] == "MARGIN_EXPANSION"
        # evidence snake→camel
        ev = first["evidence"]
        assert "triggerMetric" in ev
        assert "expansionBp" in ev
        assert ev["triggerMetric"] == "gross_margin"
        assert ev["expansionBp"] == 900

    def test_r2_no_active_triggers_returns_empty_list(self, client, db_session):
        """R2: ticker with no active triggers → 200 + triggers=[] (不报 404)."""
        resp = client.get("/api/cockpit/repricing-triggers/TSLA")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["triggers"] == []
        assert body["data"]["ticker"] == "TSLA"

    def test_r3_invalid_ticker_returns_422(self, client):
        """R3: invalid ticker chars → 422 + VALIDATION_ERROR."""
        for bad in ("aaa@@", "has space", ""):
            resp = client.get(f"/api/cockpit/repricing-triggers/{bad}")
            if bad == "":
                # empty path resolves to market endpoint — skip
                continue
            assert resp.status_code == 422, f"expected 422 for {bad!r}"
            body = resp.json()
            assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_r4_lowercase_ticker_auto_uppers(self, client, db_session):
        """R4: lowercase nvda → auto-upper, data.ticker='NVDA'."""
        _seed_trigger(db_session, ticker="NVDA", trigger_type="EARNINGS_ACCEL")

        resp = client.get("/api/cockpit/repricing-triggers/nvda")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["ticker"] == "NVDA"
        assert len(body["data"]["triggers"]) == 1


# ── TestMarketEndpoint ────────────────────────────────────────────────────────


class TestMarketEndpoint:
    def test_r5_market_wide_returns_all_triggers_sorted(self, client, db_session):
        """R5: 3 tickers × 5 trigger types (15 active rows) → totalCount=15, correct structure."""
        all_types = list(_EVIDENCE_BY_TYPE.keys())
        tickers = ["NVDA", "AAPL", "MSFT"]
        for i, ticker in enumerate(tickers):
            for j, ttype in enumerate(all_types):
                _seed_trigger(
                    db_session,
                    ticker=ticker,
                    trigger_type=ttype,
                    detected_date=date(2026, 1, 1 + i),
                    confidence=0.5 + j * 0.05,
                )

        resp = client.get("/api/cockpit/repricing-triggers")
        assert resp.status_code == 200
        body = resp.json()
        data = body["data"]
        assert data["totalCount"] == 15
        assert len(data["triggers"]) == 15
        # Each item has ticker field
        assert "ticker" in data["triggers"][0]
        # computedAt is present
        assert "computedAt" in data
        # First item has highest detectedDate (MSFT rows at 2026-01-03)
        assert data["triggers"][0]["detectedDate"] == "2026-01-03"

    def test_r6_filter_by_trigger_type(self, client, db_session):
        """R6: ?triggerType=BALANCE_INFLECTION → only BALANCE_INFLECTION rows."""
        all_types = list(_EVIDENCE_BY_TYPE.keys())
        for ttype in all_types:
            _seed_trigger(db_session, ticker="NVDA", trigger_type=ttype)

        resp = client.get("/api/cockpit/repricing-triggers?triggerType=BALANCE_INFLECTION")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["totalCount"] == 1
        assert len(data["triggers"]) == 1
        assert data["triggers"][0]["triggerType"] == "BALANCE_INFLECTION"

    def test_r7_invalid_params_return_422(self, client):
        """R7: invalid triggerType / limit=501 / limit=0 → 422."""
        for url in (
            "/api/cockpit/repricing-triggers?triggerType=INVALID",
            "/api/cockpit/repricing-triggers?limit=501",
            "/api/cockpit/repricing-triggers?limit=0",
        ):
            resp = client.get(url)
            assert resp.status_code == 422, f"expected 422 for {url}"

    def test_r8_empty_table_returns_valid_response(self, client):
        """R8: empty table → 200 + triggers=[] + totalCount=0 + valid ISO8601 UTC computedAt."""
        resp = client.get("/api/cockpit/repricing-triggers")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["triggers"] == []
        assert data["totalCount"] == 0
        computed_at = data["computedAt"]
        # Must be parseable as ISO8601 with UTC offset
        assert "T" in computed_at
        parsed = datetime.fromisoformat(computed_at.replace("Z", "+00:00"))
        assert parsed.tzinfo is not None
