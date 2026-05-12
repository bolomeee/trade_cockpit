from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models import Base


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    action = Column(String(10), nullable=False)
    price = Column(Float, nullable=False)
    date = Column(Date, nullable=False, index=True)
    position_size = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    target_price = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)
    reference = Column(Text, nullable=True)
    ai_review = Column(Text, nullable=True)
    ai_review_memo_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    stock = relationship("Stock", back_populates="journal_entries")
