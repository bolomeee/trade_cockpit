"""Monthly cost budget guard (D069): SUM ai_memos.cost_usd for current UTC month."""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.ai_memo import AiMemo

from .errors import AiBudgetExceeded


def month_to_date_cost(db: Session, *, now: datetime | None = None) -> Decimal:
    """Return SUM(cost_usd) of ai_memos created since first day of current UTC month."""
    now = now or datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = (
        db.query(func.coalesce(func.sum(AiMemo.cost_usd), 0))
        .filter(AiMemo.created_at >= month_start)
        .scalar()
    )
    return Decimal(total)


def assert_within_budget(
    db: Session,
    *,
    cap_usd: float | None = None,
    now: datetime | None = None,
) -> Decimal:
    """Raise AiBudgetExceeded when month-to-date cost ≥ cap. Returns current MTD on success.

    cap_usd defaults to settings.ai_monthly_budget_usd; passing explicit value
    is for testability (override without env juggling).
    """
    cap = Decimal(str(cap_usd if cap_usd is not None else settings.ai_monthly_budget_usd))
    mtd = month_to_date_cost(db, now=now)
    if mtd >= cap:
        raise AiBudgetExceeded(f"month_to_date={mtd} >= cap={cap}")
    return mtd
