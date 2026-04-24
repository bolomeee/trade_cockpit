from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, Date, DateTime, Float, Integer, String, UniqueConstraint

from app.models import Base


class EarningsEvent(Base):
    __tablename__ = "earnings_events"
    __table_args__ = (
        UniqueConstraint("ticker", "earnings_date", name="uq_earnings_event_ticker_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    earnings_date = Column(Date, nullable=False, index=True)
    eps_estimate = Column(Float, nullable=True)
    eps_actual = Column(Float, nullable=True)
    revenue_estimate = Column(BigInteger, nullable=True)
    revenue_actual = Column(BigInteger, nullable=True)
    time_of_day = Column(String(8), nullable=True)
    fetched_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
