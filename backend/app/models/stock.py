from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.models import Base


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    exchange = Column(String(20), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    added_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_refreshed_at = Column(DateTime, nullable=True)
    shares_float = Column(BigInteger, nullable=True)
    shares_float_refreshed_at = Column(DateTime, nullable=True)

    daily_bars = relationship("DailyBar", back_populates="stock")
    signals = relationship("Signal", back_populates="stock")
    pullbacks = relationship("Pullback", back_populates="stock")
    journal_entries = relationship("JournalEntry", back_populates="stock")
