"""EarningsService (F204-a).

Responsibilities:
- fetch_and_store: FMP /stable/earnings-calendar を増量取得して DB に upsert
- get_next_earnings: ticker の次回 earnings を返す（F204-b Router 向け dict）

消費境界：仅 backend/app/services/cockpit/ および routers/cockpit/ が import 可（D065）。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.external.fmp_client import FmpClient
from app.repositories.earnings_event_repository import EarningsEventRepository

logger = logging.getLogger(__name__)

_TIME_OF_DAY_ALLOWED = {"BMO", "AMC"}


def _normalize_time_of_day(raw: str | None) -> str | None:
    """Map FMP time field to BMO/AMC/None; discard '--' and unknown values."""
    if raw and raw.upper() in _TIME_OF_DAY_ALLOWED:
        return raw.upper()
    return None


def _parse_date(raw: str | None) -> date | None:
    """Parse YYYY-MM-DD string to date; return None on failure."""
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


class EarningsService:
    def __init__(self, db: Session, fmp: FmpClient) -> None:
        self._db = db
        self._fmp = fmp
        self._repo = EarningsEventRepository(db)

    def fetch_and_store(self, today: date | None = None) -> dict:
        """Fetch earnings from FMP and upsert into earnings_events.

        Window: from=today-7, to=today+30 (single request covering both
        the look-back補拉 and the upcoming 30-day range per DATA-MODEL D065).

        Returns {"fetched": N, "upserted": M, "date_range": [from_str, to_str]}.
        """
        if today is None:
            today = datetime.now(timezone.utc).date()

        from_date = today - timedelta(days=7)
        to_date = today + timedelta(days=30)
        from_str = from_date.isoformat()
        to_str = to_date.isoformat()

        raw = self._fmp.get_earnings_calendar(from_str, to_str)
        logger.info("earnings_calendar: fetched %d raw items (%s to %s)", len(raw), from_str, to_str)

        records: list[dict] = []
        now_utc = datetime.now(timezone.utc)

        for item in raw:
            symbol = item.get("symbol") or item.get("ticker") or ""
            if not symbol:
                continue
            event_date = _parse_date(item.get("date"))
            if event_date is None:
                continue

            eps_estimate = item.get("epsEstimated") or item.get("eps_estimated")
            eps_actual_raw = item.get("eps")
            revenue_estimate_raw = item.get("revenueEstimated") or item.get("revenue_estimated")
            revenue_actual_raw = item.get("revenue")

            records.append({
                "ticker": symbol.upper(),
                "earnings_date": event_date,
                "eps_estimate": float(eps_estimate) if eps_estimate is not None else None,
                "eps_actual": float(eps_actual_raw) if eps_actual_raw is not None else None,
                "revenue_estimate": int(revenue_estimate_raw) if revenue_estimate_raw is not None else None,
                "revenue_actual": int(revenue_actual_raw) if revenue_actual_raw is not None else None,
                "time_of_day": _normalize_time_of_day(item.get("time")),
                "fetched_at": now_utc,
            })

        upserted = self._repo.upsert_batch(records)
        logger.info("earnings_calendar: upserted %d records", upserted)
        return {"fetched": len(raw), "upserted": upserted, "date_range": [from_str, to_str]}

    def get_next_earnings(self, ticker: str) -> dict:
        """Return next earnings info for ticker (from today onward).

        Dict keys match API-CONTRACT.md camelCase:
          nextEarningsDate, daysUntil, timeOfDay, epsEstimate, revenueEstimate.
        Returns None values when no upcoming earnings found in DB.
        """
        today = datetime.now(timezone.utc).date()
        event = self._repo.get_next_earnings(ticker.upper(), today)

        if event is None:
            return {
                "ticker": ticker.upper(),
                "nextEarningsDate": None,
                "daysUntil": None,
                "timeOfDay": None,
                "epsEstimate": None,
                "revenueEstimate": None,
            }

        days_until = (event.earnings_date - today).days
        return {
            "ticker": ticker.upper(),
            "nextEarningsDate": event.earnings_date.isoformat(),
            "daysUntil": days_until,
            "timeOfDay": event.time_of_day,
            "epsEstimate": event.eps_estimate,
            "revenueEstimate": event.revenue_estimate,
        }
