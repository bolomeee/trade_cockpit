"""F105 universe refresh service (D038).

Pulls the large-cap US screener universe from FMP and upserts into
`market_scan_universe`. Independent monthly cron; failure does not affect
the daily MarketScannerService (it will keep reading whatever universe rows
exist with the last successful `last_seen_at`).
"""
from __future__ import annotations

import re
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

# SEC/FINRA convention: US open-end mutual funds use a 5-letter ticker ending
# in "X" (e.g. OAKIX, VPMAX, ABALX). FMP's screener `isFund=false` filter does
# not reliably exclude all of them — some slip through and pollute the
# breakout scan universe. This regex is a defensive ticker-shape filter
# layered on top of the FMP filter. Common stocks and ETFs do not match this
# pattern (ETFs are 2–4 letters; single-X-suffix equities like "XOM" are 3
# letters). See D052.
_MUTUAL_FUND_TICKER_RE = re.compile(r"^[A-Z]{4}X$")

from sqlalchemy.orm import Session

from app.repositories.market_scan_universe_repository import (
    MarketScanUniverseRepository,
    UniverseUpsertRow,
)
from app.repositories.system_log_repository import SystemLogRepository

LOG_SOURCE = "universe_refresher"


class _FmpClientLike(Protocol):
    def get_screener_universe(
        self,
        market_cap_gte: int = ...,
        exchanges: tuple[str, ...] = ...,
        limit_per_exchange: int = ...,
    ) -> list[dict[str, Any]]: ...


@dataclass
class UniverseRefreshResult:
    status: str  # "ok" | "error"
    upserted: int
    skipped: int
    error: str | None = None


class UniverseRefreshService:
    def __init__(self, db: Session, fmp: _FmpClientLike) -> None:
        self.db = db
        self.fmp = fmp
        self.repo = MarketScanUniverseRepository(db)
        self.log_repo = SystemLogRepository(db)

    def refresh(self) -> UniverseRefreshResult:
        try:
            raw = self.fmp.get_screener_universe()
        except Exception as exc:  # noqa: BLE001 — boundary, logged below
            self.log_repo.create(
                level="ERROR",
                source=LOG_SOURCE,
                message=f"screener fetch failed: {exc}",
                detail=traceback.format_exc(),
            )
            return UniverseRefreshResult(
                status="error", upserted=0, skipped=0, error=str(exc)
            )

        rows: list[UniverseUpsertRow] = []
        skipped = 0
        for item in raw:
            parsed = _parse_screener_row(item)
            if parsed is None:
                skipped += 1
                continue
            rows.append(parsed)

        now = datetime.now(timezone.utc)
        self.repo.upsert_many(rows, now=now)

        self.log_repo.create(
            level="OK",
            source=LOG_SOURCE,
            message=f"universe refreshed: upserted={len(rows)} skipped={skipped}",
        )
        return UniverseRefreshResult(
            status="ok", upserted=len(rows), skipped=skipped, error=None
        )


def _parse_screener_row(item: Any) -> UniverseUpsertRow | None:
    if not isinstance(item, dict):
        return None
    symbol = item.get("symbol")
    if not isinstance(symbol, str) or not symbol:
        return None
    if _MUTUAL_FUND_TICKER_RE.match(symbol):
        return None
    market_cap_raw = item.get("marketCap")
    try:
        market_cap = int(market_cap_raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if market_cap <= 0:
        return None
    company_name = item.get("companyName") or symbol
    exchange = item.get("exchange") or item.get("exchangeShortName") or ""
    return UniverseUpsertRow(
        ticker=symbol,
        company_name=str(company_name)[:200],
        exchange=str(exchange)[:20],
        market_cap=market_cap,
    )
