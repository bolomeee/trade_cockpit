from sqlalchemy import Column, Date, Float, Integer, String, UniqueConstraint

from app.models import Base


class MarketIndex(Base):
    __tablename__ = "market_indices"
    __table_args__ = (
        UniqueConstraint("symbol", "date", name="uq_market_index_symbol_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    date = Column(Date, nullable=False, index=True)
    close = Column(Float, nullable=False)
    prev_close = Column(Float, nullable=True)
    change_pct = Column(Float, nullable=True)
