from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Column, Date, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.exc import IntegrityError

from app.models import Base

ENDPOINT_CHART = "chart"
ENDPOINT_FUNDAMENTALS = "fundamentals"


class DailyPayloadCache(Base):
    __tablename__ = "daily_payload_cache"
    __table_args__ = (
        UniqueConstraint(
            "ticker", "endpoint", "as_of_date",
            name="uq_daily_payload_cache_ticker_endpoint_date",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    endpoint = Column(String(20), nullable=False)
    as_of_date = Column(Date, nullable=False)
    payload_json = Column(Text, nullable=False)
    cached_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )


def get_today_payload(db, ticker: str, endpoint: str) -> dict[str, Any] | None:
    """Return cached payload for (ticker, endpoint) if as_of_date == today, else None."""
    today = date.today()
    row = (
        db.query(DailyPayloadCache)
        .filter_by(ticker=ticker, endpoint=endpoint, as_of_date=today)
        .first()
    )
    if row is None:
        return None
    return json.loads(row.payload_json)


def upsert_today_payload(
    db, ticker: str, endpoint: str, payload: dict[str, Any]
) -> None:
    """Write payload to cache for today. Silently ignores race-condition duplicates."""
    today = date.today()
    existing = (
        db.query(DailyPayloadCache)
        .filter_by(ticker=ticker, endpoint=endpoint, as_of_date=today)
        .first()
    )
    if existing is not None:
        existing.payload_json = json.dumps(payload, default=_json_default)
        existing.cached_at = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        row = DailyPayloadCache(
            ticker=ticker,
            endpoint=endpoint,
            as_of_date=today,
            payload_json=json.dumps(payload, default=_json_default),
            cached_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
