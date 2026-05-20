"""F218-d7a: /api/cockpit/repricing-triggers — 2 endpoint (single ticker + market-wide)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.repricing_trigger import RepricingTrigger
from app.repositories.repricing_trigger_repository import RepricingTriggerRepository
from app.schemas.cockpit.repricing_trigger import (
    MarketRepricingTriggersData,
    MarketRepricingTriggersResponse,
    RepricingTriggerItem,
    RepricingTriggerItemWithTicker,
    TickerRepricingTriggersData,
    TickerRepricingTriggersResponse,
    TriggerType,
)
from app.services.watchlist_service import APIError

router = APIRouter(prefix="/repricing-triggers", tags=["cockpit-repricing"])

_TICKER_RE = re.compile(r"^[A-Z0-9.\-]+$")


def _snake_to_camel(s: str) -> str:
    head, *tail = s.split("_")
    return head + "".join(w.title() for w in tail)


def _evidence_to_camel(evidence: dict) -> dict:
    """Recursively snake_case → camelCase keys on evidence dict (values untouched)."""
    return {_snake_to_camel(k): v for k, v in evidence.items()}


def _row_to_item(row: RepricingTrigger) -> dict:
    """Map ORM row → dict suitable for RepricingTriggerItem(WithTicker) validation."""
    evidence = _evidence_to_camel(json.loads(row.evidence_json))
    computed_at = row.computed_at
    if computed_at.tzinfo is None:  # SQLite strips tzinfo; re-attach UTC
        computed_at = computed_at.replace(tzinfo=timezone.utc)
    return {
        "ticker": row.ticker,
        "trigger_type": row.trigger_type,
        "detected_date": row.detected_date.isoformat(),
        "confidence": row.confidence,
        "evidence": evidence,
        "computed_at": computed_at.isoformat(),
    }


@router.get("/{ticker}", response_model=TickerRepricingTriggersResponse)
def get_repricing_triggers_for_ticker(
    ticker: str,
    db: Session = Depends(get_db),
) -> TickerRepricingTriggersResponse:
    """Return all active triggers for the given ticker (empty list if none)."""
    upper = ticker.upper()
    if not _TICKER_RE.match(upper):
        raise APIError("VALIDATION_ERROR", f"invalid ticker: {ticker}", 422)

    rows = RepricingTriggerRepository(db).get_active_for_ticker(upper)
    items = [RepricingTriggerItem.model_validate(_row_to_item(r)) for r in rows]
    return TickerRepricingTriggersResponse(
        data=TickerRepricingTriggersData(ticker=upper, triggers=items),
    )


@router.get("", response_model=MarketRepricingTriggersResponse)
def get_repricing_triggers_market(
    trigger_type: TriggerType | None = Query(default=None, alias="triggerType"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> MarketRepricingTriggersResponse:
    """Return market-wide active triggers, optional filter by triggerType."""
    rows, total = RepricingTriggerRepository(db).get_all_active(
        trigger_type=trigger_type, limit=limit,
    )
    items = [RepricingTriggerItemWithTicker.model_validate(_row_to_item(r)) for r in rows]
    if rows:
        raw_ct = max(r.computed_at for r in rows)
        if raw_ct.tzinfo is None:
            raw_ct = raw_ct.replace(tzinfo=timezone.utc)
        computed_at = raw_ct.isoformat()
    else:
        computed_at = datetime.now(timezone.utc).isoformat()
    return MarketRepricingTriggersResponse(
        data=MarketRepricingTriggersData(
            triggers=items, total_count=total, computed_at=computed_at,
        ),
    )
