from sqlalchemy import Boolean, Column, Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models import Base


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (
        UniqueConstraint("stock_id", "date", name="uq_signal_stock_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    signal_type = Column(String(20), nullable=False)
    ma150_value = Column(Float, nullable=True)
    close_price = Column(Float, nullable=False)
    distance_pct = Column(Float, nullable=True)
    slope_positive = Column(Boolean, nullable=True)
    slope_value = Column(Float, nullable=True)

    stock = relationship("Stock", back_populates="signals")
