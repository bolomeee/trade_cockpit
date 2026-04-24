"""D070: cockpit service parameters — frozen Pydantic v2 models, no magic numbers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CockpitSharedParams(BaseModel):
    """§0 SHARED — MA periods and universe lists shared across all cockpit services."""

    model_config = ConfigDict(frozen=True)

    MA_SHORT: int = Field(default=50, description="Short-term MA period used in regime and setup scoring", ge=1, le=500)
    MA_LONG: int = Field(default=200, description="Long-term MA period used in regime and setup scoring", ge=1, le=1000)
    REGIME_LOOKBACK_DAYS: int = Field(default=200, description="Minimum history bars required for regime computation", ge=50, le=1000)
    RS_LOOKBACK_DAYS: int = Field(default=20, description="Rolling window (trading days) for RS trend comparison", ge=1, le=252)
    SECTOR_ETFS: list[str] = Field(
        default=["XLK", "XLY", "XLF", "XLI", "XLE", "XLV", "XLC", "XLP", "XLU", "XLB", "XLRE"],
        description="11 GICS sector ETFs for breadth and participation scoring",
    )
    INDEX_ETFS: list[str] = Field(
        default=["SPY", "QQQ", "IWM"],
        description="3 broad-market index ETFs (SPY/QQQ/IWM) used in trend scoring",
    )


class CockpitRegimeParams(BaseModel):
    """§1 REGIME — all scoring point values, thresholds, and recommendation tables."""

    model_config = ConfigDict(frozen=True)

    # ── SPY Trend sub-score (max 25) ──────────────────────────────────────────
    SPY_ABOVE_MA_SHORT_PTS: int = Field(default=8, description="Points when SPY close > MA50", ge=0, le=25)
    SPY_ABOVE_MA_LONG_PTS: int = Field(default=8, description="Points when SPY close > MA200", ge=0, le=25)
    SPY_GOLDEN_CROSS_PTS: int = Field(default=9, description="Points when SPY MA50 > MA200 (golden cross)", ge=0, le=25)

    # ── QQQ Trend sub-score (max 20) ──────────────────────────────────────────
    QQQ_ABOVE_MA_SHORT_PTS: int = Field(default=7, description="Points when QQQ close > MA50", ge=0, le=20)
    QQQ_ABOVE_MA_LONG_PTS: int = Field(default=6, description="Points when QQQ close > MA200", ge=0, le=20)
    QQQ_GOLDEN_CROSS_PTS: int = Field(default=7, description="Points when QQQ MA50 > MA200 (golden cross)", ge=0, le=20)

    # ── IWM Breadth sub-score (max 15) ────────────────────────────────────────
    IWM_ABOVE_MA_SHORT_PTS: int = Field(default=5, description="Points when IWM close > MA50", ge=0, le=15)
    IWM_ABOVE_MA_LONG_PTS: int = Field(default=5, description="Points when IWM close > MA200", ge=0, le=15)
    IWM_RS_POSITIVE_PTS: int = Field(default=5, description="Points when IWM/MA50 ratio > SPY/MA50 ratio (small-cap leading)", ge=0, le=15)

    # ── Risk Appetite sub-score (max 10) ─────────────────────────────────────
    XLY_ABOVE_MA_SHORT_PTS: int = Field(default=5, description="Points when XLY (consumer discretionary) close > MA50", ge=0, le=10)
    XLK_ABOVE_MA_SHORT_PTS: int = Field(default=5, description="Points when XLK (technology) close > MA50", ge=0, le=10)

    # ── Volatility Stress sub-score (max 10) ─────────────────────────────────
    SPY_RETURN_PTS: int = Field(default=5, description="Points when SPY N-day return > SPY_RETURN_MIN_PCT", ge=0, le=10)
    BREADTH_STRESS_PTS: int = Field(default=5, description="Points when ≥SECTOR_BREADTH_MIN sector ETFs are above MA50", ge=0, le=10)
    SPY_RETURN_MIN_PCT: float = Field(default=-5.0, description="SPY N-day return threshold (%); below this is stress", ge=-50.0, le=0.0)
    SECTOR_BREADTH_MIN: int = Field(default=5, description="Minimum number of sector ETFs above MA50 to avoid stress penalty", ge=1, le=11)

    # ── Regime classification thresholds ─────────────────────────────────────
    RISK_ON_MIN: int = Field(default=80, description="market_score >= this → RISK_ON", ge=1, le=100)
    CONSTRUCTIVE_MIN: int = Field(default=60, description="market_score >= this → CONSTRUCTIVE", ge=1, le=100)
    NEUTRAL_MIN: int = Field(default=40, description="market_score >= this → NEUTRAL", ge=1, le=100)
    DEFENSIVE_MIN: int = Field(default=20, description="market_score >= this → DEFENSIVE; below this → RISK_OFF", ge=0, le=100)

    # ── Sector state ratio thresholds (close / MA50) ──────────────────────────
    SECTOR_STRONG_RATIO: float = Field(default=1.02, description="close/MA50 >= this → sector state 'Strong'", ge=1.0, le=2.0)
    SECTOR_NEUTRAL_RATIO: float = Field(default=1.0, description="close/MA50 >= this (and < STRONG) → sector state 'Constructive'; below this → 'Weak' or 'Defensive'", ge=0.5, le=1.5)
    SECTOR_WEAK_RATIO: float = Field(default=0.97, description="close/MA50 >= this (and < NEUTRAL) → sector state 'Weak'; below this → 'Defensive'", ge=0.5, le=1.0)

    # ── Allowed exposure by regime ────────────────────────────────────────────
    ALLOWED_EXPOSURE_PCT: dict[str, float] = Field(
        default={
            "RISK_ON": 90.0,
            "CONSTRUCTIVE": 70.0,
            "NEUTRAL": 50.0,
            "DEFENSIVE": 30.0,
            "RISK_OFF": 10.0,
        },
        description="Recommended total portfolio exposure (%) for each regime",
    )

    # ── Single trade risk by regime ───────────────────────────────────────────
    SINGLE_TRADE_RISK_PCT: dict[str, float] = Field(
        default={
            "RISK_ON": 1.5,
            "CONSTRUCTIVE": 1.0,
            "NEUTRAL": 0.75,
            "DEFENSIVE": 0.5,
            "RISK_OFF": 0.0,
        },
        description="Maximum single-trade risk (% of portfolio) for each regime",
    )

    # ── Setup recommendations by regime ──────────────────────────────────────
    PREFERRED_SETUPS: dict[str, list[str]] = Field(
        default={
            "RISK_ON": ["BREAKOUT", "PULLBACK", "RECLAIM"],
            "CONSTRUCTIVE": ["BREAKOUT", "PULLBACK"],
            "NEUTRAL": ["PULLBACK", "RECLAIM"],
            "DEFENSIVE": ["RECLAIM"],
            "RISK_OFF": [],
        },
        description="Setup types to favour for each regime",
    )
    AVOID_SETUPS: dict[str, list[str]] = Field(
        default={
            "RISK_ON": [],
            "CONSTRUCTIVE": ["EXTENDED"],
            "NEUTRAL": ["BREAKOUT", "EXTENDED"],
            "DEFENSIVE": ["BREAKOUT", "PULLBACK", "EXTENDED"],
            "RISK_OFF": ["BREAKOUT", "PULLBACK", "RECLAIM", "EARNINGS_DRIFT", "EXTENDED"],
        },
        description="Setup types to avoid for each regime",
    )


SHARED = CockpitSharedParams()
REGIME = CockpitRegimeParams()
