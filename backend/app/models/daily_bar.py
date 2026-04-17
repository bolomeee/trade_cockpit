from sqlalchemy import BigInteger, Column, Date, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models import Base


class DailyBar(Base):
    __tablename__ = "daily_bars"
    __table_args__ = (
        UniqueConstraint("stock_id", "date", name="uq_daily_bar_stock_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(BigInteger, nullable=False)

    stock = relationship("Stock", back_populates="daily_bars")
