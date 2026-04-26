from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, Column, Date, DateTime, Float, Index, Integer, String, Text

from app.models import Base


class PendingOrder(Base):
    __tablename__ = "pending_orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'TRIGGERED', 'CANCELLED', 'EXPIRED')",
            name="ck_pending_orders_status",
        ),
        CheckConstraint("shares > 0", name="ck_pending_orders_shares_positive"),
        Index("ix_pending_orders_ticker", "ticker"),
        Index("ix_pending_orders_status", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False)
    setup_type = Column(String(24), nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_price = Column(Float, nullable=False)
    shares = Column(Integer, nullable=False)
    target_2r = Column(Float, nullable=True)
    target_3r = Column(Float, nullable=True)
    expiration_date = Column(Date, nullable=True)
    status = Column(String(16), nullable=False, default="ACTIVE")
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
