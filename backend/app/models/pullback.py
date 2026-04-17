from sqlalchemy import Column, Date, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models import Base


class Pullback(Base):
    __tablename__ = "pullbacks"
    __table_args__ = (
        UniqueConstraint("stock_id", "date", name="uq_pullback_stock_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    close_price = Column(Float, nullable=False)
    ma150_value = Column(Float, nullable=False)
    distance_pct = Column(Float, nullable=False)
    return_10d = Column(Float, nullable=True)
    return_20d = Column(Float, nullable=True)
    return_30d = Column(Float, nullable=True)

    stock = relationship("Stock", back_populates="pullbacks")
