"""F206-a: PositionService — CRUD + server-side enrichment (D041 last_close fallback)."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Callable

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.external.fmp_client import FmpClient
from app.models.earnings_event import EarningsEvent
from app.models.position import Position
from app.repositories.earnings_event_repository import EarningsEventRepository
from app.repositories.pending_order_repository import PendingOrderRepository
from app.repositories.position_repository import PositionRepository
from app.repositories.user_settings_repository import UserSettingsRepository
from app.services.watchlist_service import APIError
from app.schemas.cockpit.position import (
    PositionCreate,
    PositionItem,
    PositionSummary,
    PositionUpdate,
)
from app.services.cockpit.last_close_loader import LastCloseLoader
from app.services.cockpit.position_action_rules import compute_next_action
from app.services.cockpit.position_sizer import compute_shares

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]


def _trade_review_background(session_factory: SessionFactory, position_id: int) -> None:
    """Run in FastAPI BackgroundTask after response. Opens a fresh DB session."""
    from app.services.cockpit.journal_review_service import JournalReviewService  # noqa: PLC0415

    db = session_factory()
    try:
        JournalReviewService(db).trade_review_for_position(position_id)
    finally:
        db.close()


class PositionService:
    def __init__(
        self,
        db: Session,
        fmp: FmpClient,
    ) -> None:
        self._db = db
        self._fmp = fmp
        self._repo = PositionRepository(db)
        self._pending_repo = PendingOrderRepository(db)
        self._settings_repo = UserSettingsRepository(db)
        self._earnings_repo = EarningsEventRepository(db)
        self._loader = LastCloseLoader(db, fmp)

    # ------------------------------------------------------------------
    # Public CRUD
    # ------------------------------------------------------------------

    def list_positions(self, status: str = "open") -> tuple[PositionSummary, list[PositionItem]]:
        rows = self._repo.list_by_status(status)  # type: ignore[arg-type]

        if rows:
            tickers = [r.ticker for r in rows]
            last_closes = self._loader.load(tickers)
        else:
            last_closes = {}

        today = date.today()
        items = [
            self._enrich(
                row,
                last_closes.get(row.ticker),
                self._earnings_repo.get_next_earnings(row.ticker, today),
                include_recommended=False,
            )
            for row in rows
        ]

        # Summary is always based on OPEN positions + ACTIVE pending_orders,
        # decoupled from the ?status= filter (Q1 decision).
        if status == "open":
            open_rows = rows
            open_last_closes = last_closes
        else:
            open_rows = self._repo.list_by_status("open")  # type: ignore[arg-type]
            if open_rows:
                open_last_closes = self._loader.load([r.ticker for r in open_rows])
            else:
                open_last_closes = {}

        summary = self._compute_summary(open_rows, open_last_closes)
        return summary, items

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

    def update_position(
        self,
        position_id: int,
        patch: PositionUpdate,
        background_tasks: BackgroundTasks | None = None,
        session_factory: SessionFactory | None = None,
    ) -> PositionItem | None:
        row = self._repo.get_by_id(position_id)
        if row is None:
            return None

        pre_status = row.status
        patch_data = patch.model_dump(exclude_unset=True, by_alias=False)

        # Reject CLOSED → OPEN transition
        if patch_data.get("status") == "OPEN" and row.status == "CLOSED":
            raise APIError("VALIDATION_ERROR", "Cannot reopen a CLOSED position", 422)

        self._repo.update(position_id, patch_data)
        updated_row = self._repo.get_by_id(position_id)
        if updated_row is None:
            return None

        # F211-d1: trigger AI review on OPEN→CLOSED transition (async, fail-soft)
        if (
            pre_status == "OPEN"
            and updated_row.status == "CLOSED"
            and background_tasks is not None
            and session_factory is not None
        ):
            background_tasks.add_task(
                _trade_review_background,
                session_factory,
                int(updated_row.id),  # Column[int] at annotation-time, int at runtime
            )

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

    def _compute_summary(
        self,
        open_rows: list[Position],
        open_last_closes: dict[str, float | None],
    ) -> PositionSummary:
        """Compute the 5-field risk summary over OPEN positions + ACTIVE pending_orders."""
        account_size = self._settings_repo.get_or_default()["account_size"]
        pct_computable = account_size is not None and account_size > 0

        open_risk_raw = sum(
            (row.entry_price - row.stop_price) * row.shares for row in open_rows
        )
        total_exposure_raw = sum(
            (open_last_closes.get(row.ticker) or 0.0) * row.shares for row in open_rows
        )

        active_pending = self._pending_repo.list_by_status("ACTIVE")
        pending_risk_raw = sum(
            (row.entry_price - row.stop_price) * row.shares for row in active_pending
        )

        if pct_computable:
            open_risk_pct: float | None = round(open_risk_raw / account_size * 100, 2)
            total_exposure_pct: float | None = round(total_exposure_raw / account_size * 100, 2)
            pending_risk_pct: float | None = round(pending_risk_raw / account_size * 100, 2)
        else:
            open_risk_pct = None
            total_exposure_pct = None
            pending_risk_pct = None

        return PositionSummary(
            open_risk_pct=open_risk_pct,
            total_exposure_pct=total_exposure_pct,
            pending_risk_pct=pending_risk_pct,
            positions_count=len(open_rows),
            pending_count=len(active_pending),
        )
