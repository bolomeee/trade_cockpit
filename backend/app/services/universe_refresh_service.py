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

# Preferred depositary shares slip through FMP's isFund=false filter because
# FMP classifies them as ordinary securities. Their legal names always contain
# characteristic phrases. Matching any one phrase is sufficient to exclude.
_PREFERRED_SHARE_RE = re.compile(
    r"Depositary Shares|Preferred Stock|Non-Cumulative|Perpetual Preferred",
    re.IGNORECASE,
)

from sqlalchemy.orm import Session

from app.repositories.market_scan_universe_repository import (
    MarketScanUniverseRepository,
    UniverseUpsertRow,
)
from app.repositories.system_log_repository import SystemLogRepository

LOG_SOURCE = "universe_refresher"

# Mutable single-element list used as a thread-local-free counter to signal
# unexpected parse exceptions from _parse_screener_row back to refresh().
# reset to 0 after each refresh() call.
_PARSE_EXCEPTION_COUNTER: list[int] = [0]


class _FmpClientLike(Protocol):
    def get_screener_universe(
        self,
        market_cap_gte: int = ...,
        exchanges: tuple[str, ...] = ...,
        page_size: int = ...,
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
        sector_missing = 0
        industry_missing = 0
        price_missing = 0
        volume_missing = 0
        parse_exception = 0

        for item in raw:
            parsed = _parse_screener_row(item)
            if parsed is None:
                skipped += 1
                continue
            if parsed.sector is None:
                sector_missing += 1
            if parsed.industry is None:
                industry_missing += 1
            if parsed.last_price is None:
                price_missing += 1
            if parsed.last_volume is None:
                volume_missing += 1
            rows.append(parsed)

        parse_exception = _PARSE_EXCEPTION_COUNTER[0]
        _PARSE_EXCEPTION_COUNTER[0] = 0  # reset for next call

        now = datetime.now(timezone.utc)
        self.repo.upsert_many(rows, now=now)

        self.log_repo.create(
            level="OK",
            source=LOG_SOURCE,
            message=(
                f"universe refreshed: upserted={len(rows)} skipped={skipped}"
                f" sector_missing={sector_missing} industry_missing={industry_missing}"
                f" price_missing={price_missing} volume_missing={volume_missing}"
            ),
        )
        if parse_exception > 0:
            self.log_repo.create(
                level="WARN",
                source=LOG_SOURCE,
                message=f"universe refresh: unexpected parse errors parse_exception={parse_exception}",
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
    if _PREFERRED_SHARE_RE.search(str(company_name)):
        return None
    exchange = item.get("exchange") or item.get("exchangeShortName") or ""

    # Optional fields: degrade to None on missing or bad type rather than
    # skipping the ticker. FMP ETFs routinely omit sector/industry; price/volume
    # can arrive as "N/A" strings when the screener snapshot is stale.
    try:
        sector_raw = item.get("sector")
        sector: str | None = str(sector_raw)[:64] if sector_raw else None

        industry_raw = item.get("industry")
        industry: str | None = str(industry_raw)[:128] if industry_raw else None

        price_raw = item.get("price")
        try:
            last_price: float | None = float(price_raw) if price_raw is not None else None  # type: ignore[arg-type]
        except (TypeError, ValueError):
            last_price = None  # e.g. "N/A" string from stale screener snapshot

        volume_raw = item.get("volume")
        try:
            last_volume: int | None = int(volume_raw) if volume_raw is not None else None  # type: ignore[arg-type]
        except (TypeError, ValueError):
            last_volume = None
    except Exception:  # noqa: BLE001 — hard guard; unexpected schema breakage
        _PARSE_EXCEPTION_COUNTER[0] += 1
        return None

    return UniverseUpsertRow(
        ticker=symbol,
        company_name=str(company_name)[:200],
        exchange=str(exchange)[:20],
        market_cap=market_cap,
        sector=sector,
        industry=industry,
        last_price=last_price,
        last_volume=last_volume,
    )
