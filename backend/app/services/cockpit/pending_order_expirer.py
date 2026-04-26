"""F206-b2: APScheduler tick — auto-expire ACTIVE pending_orders past expiration_date."""
from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.repositories.pending_order_repository import PendingOrderRepository

logger = logging.getLogger(__name__)


def expire_due_pending_orders(db: Session, today: date | None = None) -> int:
    """Scan ACTIVE pending_orders with expiration_date < today, set status=EXPIRED.

    Returns number of rows updated. Idempotent (re-runs return 0).
    expiration_date IS NULL rows are never expired (no expiry = perpetual).
    """
    today = today or date.today()
    repo = PendingOrderRepository(db)
    rows = repo.list_by_status("ACTIVE")
    expired = 0
    for row in rows:
        if row.expiration_date is not None and row.expiration_date < today:
            repo.update(row.id, {"status": "EXPIRED"})
            expired += 1
    if expired > 0:
        logger.info("F206-b2 expirer: marked %d pending_orders as EXPIRED", expired)
    return expired
