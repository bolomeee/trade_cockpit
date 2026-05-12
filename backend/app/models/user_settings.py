from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, Float, Integer, String

from app.models import Base


class UserSettings(Base):
    __tablename__ = "user_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_user_settings_single_row"),
    )

    id = Column(Integer, primary_key=True)
    account_size = Column(Float, nullable=False, default=100000.0)
    max_exposure_pct = Column(Float, nullable=False, default=80.0)
    single_trade_risk_pct = Column(Float, nullable=False, default=1.0)
    default_risk_per_trade_pct = Column(Float, nullable=False, default=0.75)
    base_currency = Column(String(8), nullable=False, default="USD")
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
