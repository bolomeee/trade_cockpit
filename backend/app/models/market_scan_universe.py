from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, Integer, String

from app.models import Base


class MarketScanUniverse(Base):
    __tablename__ = "market_scan_universe"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, unique=True, index=True)
    company_name = Column(String(200), nullable=False)
    exchange = Column(String(20), nullable=False)
    market_cap = Column(BigInteger, nullable=False)
    last_seen_at = Column(DateTime, nullable=False)
    added_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
