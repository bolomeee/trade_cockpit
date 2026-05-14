from __future__ import annotations

from datetime import datetime, timezone
from datetime import date as date_type

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class SetupSnapshot(Base):
    __tablename__ = "setup_snapshots"
    __table_args__ = (
        UniqueConstraint("ticker", "scan_date", name="uq_setup_snapshot_ticker_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    scan_date: Mapped[date_type] = mapped_column(Date, nullable=False, index=True)
    setup_type: Mapped[str] = mapped_column(String(24), nullable=False)
    setup_quality: Mapped[str | None] = mapped_column(String(1), nullable=True)
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_2r: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_3r: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_to_entry_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    reward_risk: Mapped[float | None] = mapped_column(Float, nullable=True)
    rs_percentile: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_status: Mapped[str | None] = mapped_column(String(8), nullable=True)
    trend_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    earnings_risk: Mapped[str] = mapped_column(String(8), nullable=False)
    ready_signal: Mapped[bool] = mapped_column(Boolean, nullable=False)
    suggested_action: Mapped[str | None] = mapped_column(String(16), nullable=True)
    volume_zscore: Mapped[float | None] = mapped_column(Float, nullable=True)
    obv_trend: Mapped[str | None] = mapped_column(String(4), nullable=True)
    up_down_volume_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    weekly_stage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
