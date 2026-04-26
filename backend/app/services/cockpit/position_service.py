"""F206-a: PositionService — CRUD + server-side enrichment (D041 last_close fallback)."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.external.fmp_client import FmpClient
from app.models.earnings_event import EarningsEvent
from app.models.position import Position
from app.repositories.earnings_event_repository import EarningsEventRepository
from app.repositories.position_repository import PositionRepository
from app.repositories.user_settings_repository import UserSettingsRepository
from app.services.watchlist_service import APIError
from app.schemas.cockpit.position import (
    PositionCreate,
    PositionItem,
    PositionUpdate,
)
from app.services.cockpit.last_close_loader import LastCloseLoader
from app.services.cockpit.position_action_rules import compute_next_action
from app.services.cockpit.position_sizer import compute_shares

logger = logging.getLogger(__name__)


class PositionService:
    def __init__(
        self,
        db: Session,
        fmp: FmpClient,
    ) -> None:
        self._db = db
        self._fmp = fmp
        self._repo = PositionRepository(db)
        self._settings_repo = UserSettingsRepository(db)
        self._earnings_repo = EarningsEventRepository(db)
        self._loader = LastCloseLoader(db, fmp)

    # ------------------------------------------------------------------
    # Public CRUD
    # ------------------------------------------------------------------

    def list_positions(self, status: str = "open") -> list[PositionItem]:
        rows = self._repo.list_by_status(status)  # type: ignore[arg-type]
        if not rows:
            return []

        tickers = [r.ticker for r in rows]
        last_closes = self._loader.load(tickers)

        today = date.today()
        return [
            self._enrich(
                row,
                last_closes.get(row.ticker),
                self._earnings_repo.get_next_earnings(row.ticker, today),
                include_recommended=False,
            )
            for row in rows
        ]

    def get_position(self, position_id: int) -> PositionItem | None:
        row = self._repo.get_by_id(position_id)
        if row is None:
            return None
        closes = self._loader.load([row.ticker])
        today = date.today()
        return self._enrich(
            row,
            closes.get(row.ticker),
            self._earnings_repo.get_next_earnings(row.ticker, today),
            include_recommended=False,
        )

    def create_position(self, payload: PositionCreate) -> PositionItem:
        data = payload.model_dump(by_alias=False)
        row = self._repo.create(data)

        closes = self._loader.load([row.ticker])
        today = date.today()
        item = self._enrich(
            row,
            closes.get(row.ticker),
            self._earnings_repo.get_next_earnings(row.ticker, today),
            include_recommended=True,
        )
        return item

    def update_position(self, position_id: int, patch: PositionUpdate) -> PositionItem | None:
        row = self._repo.get_by_id(position_id)
        if row is None:
            return None

        patch_data = patch.model_dump(exclude_unset=True, by_alias=False)

        # Reject CLOSED → OPEN transition
        if patch_data.get("status") == "OPEN" and row.status == "CLOSED":
            raise APIError("VALIDATION_ERROR", "Cannot reopen a CLOSED position", 422)

        self._repo.update(position_id, patch_data)
        updated_row = self._repo.get_by_id(position_id)
        if updated_row is None:
            return None

        closes = self._loader.load([updated_row.ticker])
        today = date.today()
        return self._enrich(
            updated_row,
            closes.get(updated_row.ticker),
            self._earnings_repo.get_next_earnings(updated_row.ticker, today),
            include_recommended=False,
        )

    def delete_position(self, position_id: int) -> bool:
        return self._repo.delete(position_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_metrics(
        self,
        row: Position,
        last_close: float | None,
        earnings_event: EarningsEvent | None,
        include_recommended: bool,
    ) -> dict[str, Any]:
        """Compute all server-side calculated fields; returns a flat dict."""
        today = date.today()

        r_multiple: float | None = None
        unrealized_pl: float | None = None
        position_value: float | None = None
        if last_close is not None:
            risk = row.entry_price - row.stop_price
            if risk > 0:
                r_multiple = round((last_close - row.entry_price) / risk, 2)
            unrealized_pl = round((last_close - row.entry_price) * row.shares, 2)
            position_value = round(last_close * row.shares, 2)

        earnings_date_str: str | None = None
        days_until_earnings: int | None = None
        if earnings_event is not None:
            earnings_date_str = str(earnings_event.earnings_date)
            days_until_earnings = (earnings_event.earnings_date - today).days

        next_action = compute_next_action(
            last_close=last_close,
            entry_price=row.entry_price,
            stop_price=row.stop_price,
            days_until_earnings=days_until_earnings,
        )

        recommended_shares: int | None = None
        if include_recommended:
            settings = self._settings_repo.get_or_default()
            recommended_shares = compute_shares(
                account_size=settings["account_size"],
                risk_pct=settings["default_risk_per_trade_pct"],
                entry=row.entry_price,
                stop=row.stop_price,
            )

        return dict(
            last_close=last_close,
            r_multiple=r_multiple,
            unrealized_pl=unrealized_pl,
            position_value=position_value,
            earnings_date=earnings_date_str,
            days_until_earnings=days_until_earnings,
            next_action=next_action,
            recommended_shares=recommended_shares,
        )

    def _enrich(
        self,
        row: Position,
        last_close: float | None,
        earnings_event: EarningsEvent | None,
        *,
        include_recommended: bool,
    ) -> PositionItem:
        metrics = self._compute_metrics(row, last_close, earnings_event, include_recommended)
        return PositionItem(
            id=row.id,
            ticker=row.ticker,
            entry_price=row.entry_price,
            entry_date=row.entry_date,
            shares=row.shares,
            stop_price=row.stop_price,
            target_2r=row.target_2r,
            target_3r=row.target_3r,
            setup_type=row.setup_type,
            notes=row.notes,
            status=row.status,
            closed_at=row.closed_at,
            close_price=row.close_price,
            created_at=row.created_at,
            updated_at=row.updated_at,
            **metrics,
        )
