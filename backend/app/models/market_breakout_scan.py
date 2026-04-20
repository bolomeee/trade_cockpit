from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    UniqueConstraint,
)

from app.models import Base


class MarketBreakoutScan(Base):
    __tablename__ = "market_breakout_scans"
    __table_args__ = (
        UniqueConstraint("scan_date", "ticker", name="uq_breakout_scan_date_ticker"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_date = Column(Date, nullable=False, index=True)
    ticker = Column(String(10), nullable=False)
    company_name = Column(String(200), nullable=False)
    close_price = Column(Float, nullable=False)
    ma150_value = Column(Float, nullable=False)
    pct_above_ma150 = Column(Float, nullable=False)
    slope_value = Column(Float, nullable=False)
    market_cap = Column(BigInteger, nullable=False)
    scanned_at = Column(DateTime, nullable=False, index=True)
