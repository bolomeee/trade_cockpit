from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, Column, Date, DateTime, Float, Index, Integer, String, Text

from app.models import Base


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (
        CheckConstraint("status IN ('OPEN', 'CLOSED')", name="ck_positions_status"),
        CheckConstraint("shares > 0", name="ck_positions_shares_positive"),
        Index("ix_positions_ticker", "ticker"),
        Index("ix_positions_status", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False)
    entry_price = Column(Float, nullable=False)
    entry_date = Column(Date, nullable=False)
    shares = Column(Integer, nullable=False)
    stop_price = Column(Float, nullable=False)
    target_2r = Column(Float, nullable=True)
    target_3r = Column(Float, nullable=True)
    setup_type = Column(String(24), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String(8), nullable=False, default="OPEN")
    closed_at = Column(DateTime(timezone=True), nullable=True)
    close_price = Column(Float, nullable=True)
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
