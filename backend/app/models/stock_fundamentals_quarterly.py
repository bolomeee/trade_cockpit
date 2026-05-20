"""F218-d6a: StockFundamentalsQuarterly ORM model.

Caches quarterly balance-sheet + cash-flow data for T5 Balance Sheet Inflection detector.
Schema 1:1 with DATA-MODEL.md §StockFundamentalsQuarterly (lines 1216-1235).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, Date, DateTime, Integer, String, UniqueConstraint

from app.models import Base


class StockFundamentalsQuarterly(Base):
    __tablename__ = "stock_fundamentals_quarterly"
    __table_args__ = (
        UniqueConstraint("ticker", "fiscal_quarter", name="uq_fundamentals_ticker_quarter"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ticker          = Column(String(10), nullable=False, index=True)
    fiscal_quarter  = Column(String(12), nullable=False)      # e.g. "Q2 2026"
    period_end_date = Column(Date, nullable=False)
    total_debt      = Column(BigInteger, nullable=True)
    cash            = Column(BigInteger, nullable=True)
    net_debt        = Column(BigInteger, nullable=True)        # service 层算 (total_debt - cash)
    fcf             = Column(BigInteger, nullable=True)
    fetched_at      = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
