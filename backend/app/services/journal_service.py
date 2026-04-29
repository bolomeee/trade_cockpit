from __future__ import annotations

import json
from typing import Any

from app.models import JournalEntry
from app.repositories.journal_repository import JournalRepository
from app.repositories.stock_repository import StockRepository
from app.services.watchlist_service import APIError

VALID_ACTIONS = {"BUY", "SELL", "ADD", "REDUCE", "WATCH"}
LIMIT_MAX = 200
LIMIT_DEFAULT = 50


class JournalService:
    def __init__(self, journal_repo: JournalRepository, stock_repo: StockRepository) -> None:
        self.journal_repo = journal_repo
        self.stock_repo = stock_repo

    def list(
        self,
        ticker: str | None,
        action: str | None,
        limit: int | None,
        offset: int | None,
    ) -> dict[str, Any]:
        norm_ticker = ticker.strip().upper() if ticker else None
        norm_action = self._normalize_action(action) if action else None
        capped_limit = max(1, min(limit or LIMIT_DEFAULT, LIMIT_MAX))
        safe_offset = max(0, offset or 0)

        entries = self.journal_repo.list(
            ticker=norm_ticker, action=norm_action, limit=capped_limit, offset=safe_offset
        )
        total = self.journal_repo.count(ticker=norm_ticker, action=norm_action)
        return {
            "items": [self._to_dto(e) for e in entries],
            "total": total,
            "limit": capped_limit,
            "offset": safe_offset,
        }

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        ticker = self._require_ticker(payload.get("ticker"))
        action = self._require_action(payload.get("action"))
        stock = self._require_watchlist_stock(ticker)

        fields = {
            "action": action,
            "price": payload["price"],
            "date": payload["date"],
            "position_size": payload.get("position_size"),
            "stop_loss": payload.get("stop_loss"),
            "target_price": payload.get("target_price"),
            "reason": payload.get("reason"),
            "reference": payload.get("reference"),
        }
        entry = self.journal_repo.create(stock_id=stock.id, fields=fields)
        return self._to_dto(entry)

    def update(self, entry_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        entry = self.journal_repo.get_by_id(entry_id)
        if entry is None:
            raise APIError("NOT_FOUND", f"journal entry {entry_id} not found", 404)

        fields: dict[str, Any] = {}
        if "ticker" in payload and payload["ticker"] is not None:
            ticker = self._require_ticker(payload["ticker"])
            stock = self._require_watchlist_stock(ticker)
            fields["stock_id"] = stock.id
        if "action" in payload and payload["action"] is not None:
            fields["action"] = self._require_action(payload["action"])
        for key in ("price", "date", "position_size", "stop_loss", "target_price", "reason", "reference"):
            if key in payload:
                fields[key] = payload[key]

        if fields:
            entry = self.journal_repo.update(entry, fields)
        return self._to_dto(entry)

    def delete(self, entry_id: int) -> int:
        entry = self.journal_repo.get_by_id(entry_id)
        if entry is None:
            raise APIError("NOT_FOUND", f"journal entry {entry_id} not found", 404)
        self.journal_repo.delete(entry)
        return entry_id

    # --- helpers ---------------------------------------------------------------

    def _require_ticker(self, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise APIError("VALIDATION_ERROR", "ticker is required", 422)
        return value.strip().upper()

    def _require_action(self, value: Any) -> str:
        action = self._normalize_action(value)
        if action not in VALID_ACTIONS:
            raise APIError(
                "VALIDATION_ERROR",
                f"action must be one of {sorted(VALID_ACTIONS)}",
                422,
            )
        return action

    def _normalize_action(self, value: Any) -> str:
        return value.strip().upper() if isinstance(value, str) else ""

    def _require_watchlist_stock(self, ticker: str):
        stock = self.stock_repo.get_by_ticker(ticker)
        if stock is None or not stock.is_active:
            raise APIError("NOT_FOUND", f"ticker {ticker} not in watchlist", 404)
        return stock

    def _to_dto(self, entry: JournalEntry) -> dict[str, Any]:
        ai_review = None
        if entry.ai_review:
            try:
                ai_review = json.loads(entry.ai_review)
            except (json.JSONDecodeError, TypeError):
                ai_review = None  # corrupt JSON in DB → silent null
        return {
            "id": entry.id,
            "ticker": entry.stock.ticker,
            "stock_name": entry.stock.name,
            "action": entry.action,
            "price": entry.price,
            "date": entry.date,
            "position_size": entry.position_size,
            "stop_loss": entry.stop_loss,
            "target_price": entry.target_price,
            "reason": entry.reason,
            "reference": entry.reference,
            "ai_review": ai_review,
            "ai_review_memo_id": entry.ai_review_memo_id,
            "created_at": entry.created_at,
            "updated_at": entry.updated_at,
        }
