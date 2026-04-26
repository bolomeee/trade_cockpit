"""F206-b1: PendingOrderService — CRUD + server-side enrichment (state machine + riskPct)."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.external.fmp_client import FmpClient
from app.models.pending_order import PendingOrder
from app.repositories.pending_order_repository import PendingOrderRepository
from app.repositories.user_settings_repository import UserSettingsRepository
from app.services.cockpit.last_close_loader import LastCloseLoader
from app.services.watchlist_service import APIError
from app.schemas.cockpit.pending_order import (
    PendingOrderCreate,
    PendingOrderItem,
    PendingOrderUpdate,
)

logger = logging.getLogger(__name__)

_VALID_STATUSES = {"ACTIVE", "TRIGGERED", "CANCELLED", "EXPIRED", "ALL"}
_TERMINAL_STATUSES = {"TRIGGERED", "CANCELLED", "EXPIRED"}


class PendingOrderService:
    def __init__(self, db: Session, fmp: FmpClient) -> None:
        self._db = db
        self._fmp = fmp
        self._repo = PendingOrderRepository(db)
        self._settings_repo = UserSettingsRepository(db)
        self._loader = LastCloseLoader(db, fmp)

    # ------------------------------------------------------------------
    # Public CRUD
    # ------------------------------------------------------------------

    def list_pending_orders(self, status: str = "active") -> list[PendingOrderItem]:
        repo_status = self._normalize_status(status)
        rows = self._repo.list_by_status(repo_status)
        if not rows:
            return []
        tickers = [r.ticker for r in rows]
        last_closes = self._loader.load(tickers)
        account_size = self._settings_repo.get_or_default()["account_size"]
        return [self._enrich(row, last_closes.get(row.ticker), account_size) for row in rows]

    def get_pending_order(self, order_id: int) -> PendingOrderItem | None:
        row = self._repo.get_by_id(order_id)
        if row is None:
            return None
        closes = self._loader.load([row.ticker])
        account_size = self._settings_repo.get_or_default()["account_size"]
        return self._enrich(row, closes.get(row.ticker), account_size)

    def create_pending_order(self, payload: PendingOrderCreate) -> PendingOrderItem:
        data = payload.model_dump(by_alias=False)
        row = self._repo.create(data)
        closes = self._loader.load([row.ticker])
        account_size = self._settings_repo.get_or_default()["account_size"]
        return self._enrich(row, closes.get(row.ticker), account_size)

    def update_pending_order(self, order_id: int, patch: PendingOrderUpdate) -> PendingOrderItem | None:
        row = self._repo.get_by_id(order_id)
        if row is None:
            return None

        patch_data = patch.model_dump(exclude_unset=True, by_alias=False)

        # State machine: terminal states cannot change status
        new_status = patch_data.get("status")
        if new_status is not None and new_status != row.status:
            if row.status in _TERMINAL_STATUSES:
                raise APIError(
                    "VALIDATION_ERROR",
                    f"Cannot change status of a {row.status} order",
                    422,
                )

        # Merged entry/stop validation (service merges with DB values if only one is patched)
        if "entry_price" in patch_data or "stop_price" in patch_data:
            entry = patch_data.get("entry_price", row.entry_price)
            stop = patch_data.get("stop_price", row.stop_price)
            if entry <= stop:
                raise APIError("VALIDATION_ERROR", "entryPrice must be greater than stopPrice", 422)

        self._repo.update(order_id, patch_data)
        updated = self._repo.get_by_id(order_id)
        if updated is None:
            return None

        closes = self._loader.load([updated.ticker])
        account_size = self._settings_repo.get_or_default()["account_size"]
        return self._enrich(updated, closes.get(updated.ticker), account_size)

    def delete_pending_order(self, order_id: int) -> bool:
        return self._repo.delete(order_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalize_status(self, raw: str) -> str:
        """Uppercase and validate status query param. Returns repo-ready value."""
        normalized = raw.upper()
        if normalized not in _VALID_STATUSES:
            raise APIError("VALIDATION_ERROR", f"Invalid status filter: {raw!r}", 422)
        return "all" if normalized == "ALL" else normalized

    def _enrich(self, row: PendingOrder, last_close: float | None, account_size: float) -> PendingOrderItem:
        distance_to_trigger_pct: float | None = None
        if last_close is not None:
            distance_to_trigger_pct = round(
                (row.entry_price - last_close) / last_close * 100, 2
            )

        risk_pct = round(
            (row.entry_price - row.stop_price) * row.shares / account_size * 100, 2
        )

        return PendingOrderItem(
            id=row.id,
            ticker=row.ticker,
            setup_type=row.setup_type,
            entry_price=row.entry_price,
            stop_price=row.stop_price,
            shares=row.shares,
            target_2r=row.target_2r,
            target_3r=row.target_3r,
            expiration_date=row.expiration_date,
            status=row.status,
            notes=row.notes,
            created_at=row.created_at,
            updated_at=row.updated_at,
            last_close=last_close,
            distance_to_trigger_pct=distance_to_trigger_pct,
            risk_pct=risk_pct,
        )
