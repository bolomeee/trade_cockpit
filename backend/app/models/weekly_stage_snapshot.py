"""F216-b: WeeklyStageSnapshot ORM model — Stan Weinstein Stage 1-4 per-ticker weekly snapshot."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Float, Integer, String, UniqueConstraint

from app.models import Base


class WeeklyStageSnapshot(Base):
    __tablename__ = "weekly_stage_snapshots"
    __table_args__ = (
        UniqueConstraint("ticker", "scan_date", name="uq_weekly_stage_ticker_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    scan_date = Column(Date, nullable=False, index=True)  # 本周最后实际交易日（NP4）
    stage = Column(Integer, nullable=False)               # 0=UNKNOWN, 1-4（NP3）
    weekly_close = Column(Float, nullable=True)
    weekly_ma_10 = Column(Float, nullable=True)
    weekly_ma_30 = Column(Float, nullable=True)
    weekly_ma_40 = Column(Float, nullable=True)
    slope_30w = Column(Float, nullable=True)              # %/周，OLS 归一化（NP2）
    computed_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
