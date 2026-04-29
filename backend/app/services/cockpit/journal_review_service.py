"""F211-d1: JournalReviewService — generate AI review for closed positions.

trade mode: single-position post-exit review.
monthly mode留给 F211-d2。
"""
from __future__ import annotations

import json
import logging
from typing import Callable

from sqlalchemy.orm import Session

from app.ai.errors import AiBudgetExceeded, AiGuardrailViolation, AiProviderError, AiSchemaError
from app.ai.gateway import AiGateway
from app.models.journal_entry import JournalEntry
from app.models.position import Position
from app.models.stock import Stock

logger = logging.getLogger(__name__)
SessionFactory = Callable[[], Session]


class JournalReviewService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._gateway = AiGateway(db)

    def trade_review_for_position(self, position_id: int) -> int | None:
        """Background-task-safe entry. Returns journal_entry_id on success, None on any failure."""
        try:
            position = self._db.get(Position, position_id)
            if position is None or position.status != "CLOSED":
                logger.warning(
                    "trade_review skipped: position %s not found or not CLOSED", position_id
                )
                return None

            stock = self._db.query(Stock).filter(Stock.ticker == position.ticker).first()
            if stock is None:
                logger.warning(
                    "trade_review skipped: ticker %s not in watchlist", position.ticker
                )
                return None

            entry = self._upsert_sell_journal_entry(stock_id=stock.id, position=position)
            if entry.ai_review:
                logger.info(
                    "trade_review skipped: journal_entry %s already has ai_review", entry.id
                )
                return entry.id

            input_dict = self._build_trade_input(position)
            result = self._gateway.run(task_type="journal_assistant", input_dict=input_dict)

            entry.ai_review = json.dumps(result.output, ensure_ascii=False, sort_keys=True)
            entry.ai_review_memo_id = result.memo_id
            self._db.commit()
            return entry.id

        except (AiProviderError, AiSchemaError, AiGuardrailViolation, AiBudgetExceeded) as e:
            logger.warning(
                "trade_review AI error position=%s: %s: %s", position_id, type(e).__name__, e
            )
            self._db.rollback()
            return None
        except Exception:  # noqa: BLE001 — top boundary, must not raise into BackgroundTask runtime
            logger.exception("trade_review unexpected error position=%s", position_id)
            self._db.rollback()
            return None

    def _upsert_sell_journal_entry(self, *, stock_id: int, position: Position) -> JournalEntry:
        """Find or create a SELL journal_entry on the close date for this ticker."""
        close_date = position.closed_at.date() if position.closed_at else position.updated_at.date()
        existing = (
            self._db.query(JournalEntry)
            .filter(
                JournalEntry.stock_id == stock_id,
                JournalEntry.action == "SELL",
                JournalEntry.date == close_date,
            )
            .order_by(JournalEntry.id.asc())
            .first()
        )
        if existing is not None:
            return existing
        entry = JournalEntry(
            stock_id=stock_id,
            action="SELL",
            price=position.close_price,
            date=close_date,
            position_size=float(position.shares),
            stop_loss=position.stop_price,
            target_price=position.target_2r,
            reason="auto: position closed",
            reference=None,
        )
        self._db.add(entry)
        self._db.flush()  # populate id without commit (commit happens after AI succeeds)
        return entry

    def _build_trade_input(self, position: Position) -> dict:
        entry_date = position.entry_date.isoformat()
        exit_date = (position.closed_at or position.updated_at).date().isoformat()
        holding_days = (
            (position.closed_at.date() - position.entry_date).days
            if position.closed_at
            else 0
        )
        risk_per_share = position.entry_price - position.stop_price
        r_multiple = (
            round((position.close_price - position.entry_price) / risk_per_share, 2)
            if risk_per_share > 0
            else 0.0
        )
        return {
            "mode": "trade",
            "trade": {
                "ticker": position.ticker,
                "setupType": position.setup_type,
                "setupQuality": None,
                "plannedEntry": position.entry_price,
                "plannedStop": position.stop_price,
                "plannedTarget2r": position.target_2r,
                "actualEntry": position.entry_price,
                "actualExit": position.close_price,
                "shares": position.shares,
                "entryDate": entry_date,
                "exitDate": exit_date,
                "holdingDays": max(holding_days, 0),
                "rMultiple": r_multiple,
                "preTradeNotes": position.notes or None,
            },
        }
