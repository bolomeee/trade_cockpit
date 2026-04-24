from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Float, Integer, Text, String, UniqueConstraint

from app.models import Base


class MarketRegimeSnapshot(Base):
    __tablename__ = "market_regime_snapshots"
    __table_args__ = (
        UniqueConstraint("date", name="uq_market_regime_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    regime = Column(String(16), nullable=False)
    market_score = Column(Integer, nullable=False)
    spy_trend_score = Column(Integer, nullable=False)
    qqq_trend_score = Column(Integer, nullable=False)
    iwm_breadth_score = Column(Integer, nullable=False)
    sector_participation_score = Column(Integer, nullable=False)
    risk_appetite_score = Column(Integer, nullable=False)
    volatility_stress_score = Column(Integer, nullable=False)
    allowed_exposure_pct = Column(Float, nullable=False)
    single_trade_risk_pct = Column(Float, nullable=False)
    preferred_setups = Column(Text, nullable=False)   # JSON array string
    avoid_setups = Column(Text, nullable=False)       # JSON array string
    computed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
