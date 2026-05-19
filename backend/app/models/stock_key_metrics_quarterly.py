"""F218-d3a: StockKeyMetricsQuarterly ORM model.

Caches quarterly income-statement derived margins for T2 Margin Expansion detector.
Schema 1:1 with DATA-MODEL.md §StockKeyMetricsQuarterly (lines 1163-1183).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Float, Integer, String, UniqueConstraint

from app.models import Base


class StockKeyMetricsQuarterly(Base):
    __tablename__ = "stock_key_metrics_quarterly"
    __table_args__ = (
        UniqueConstraint("ticker", "fiscal_quarter", name="uq_key_metrics_ticker_quarter"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ticker          = Column(String(10), nullable=False, index=True)
    fiscal_quarter  = Column(String(12), nullable=False)      # e.g. "Q1 2026"
    period_end_date = Column(Date, nullable=False)
    gross_margin    = Column(Float, nullable=True)
    op_margin       = Column(Float, nullable=True)
    net_margin      = Column(Float, nullable=True)
    fcf_margin      = Column(Float, nullable=True)
    roic            = Column(Float, nullable=True)
    fetched_at      = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
