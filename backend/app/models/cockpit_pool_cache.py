from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Index, Text

from app.models import Base


class CockpitPoolCache(Base):
    __tablename__ = "cockpit_pool_cache"

    ticker = Column(Text, primary_key=True)
    rs_percentile = Column(Float, nullable=False)
    ma50 = Column(Float, nullable=True)
    last_close = Column(Float, nullable=True)
    revenue_growth_yoy = Column(Float, nullable=True)
    computed_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_cockpit_pool_cache_computed_at", "computed_at"),
    )
