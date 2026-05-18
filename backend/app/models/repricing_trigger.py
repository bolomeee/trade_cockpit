"""F218-d1: RepricingTrigger ORM model — cockpit Phase D 5-class repricing signal per ticker."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, Integer, String, Text, UniqueConstraint,
)

from app.models import Base


class RepricingTrigger(Base):
    __tablename__ = "repricing_triggers"
    __table_args__ = (
        UniqueConstraint(
            "ticker", "trigger_type", "detected_date",
            name="uq_repricing_trigger_ticker_type_date",
        ),
    )

    id            = Column(Integer, primary_key=True, autoincrement=True)
    ticker        = Column(String(10), nullable=False, index=True)
    trigger_type  = Column(String(24), nullable=False)
    detected_date = Column(Date, nullable=False, index=True)
    confidence    = Column(Float, nullable=False, default=0.5)
    evidence_json = Column(Text, nullable=False)
    active        = Column(Boolean, nullable=False, default=True, index=True)
    computed_at   = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
