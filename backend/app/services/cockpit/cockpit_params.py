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
    SECTOR_TO_ETF: dict[str, str] = Field(
        default={
            # FMP /profile.sector 原文（11 类，2026-05-20 dev DB 实测） → 11 GICS sector ETF
            "Technology": "XLK",
            "Consumer Cyclical": "XLY",
            "Financial Services": "XLF",
            "Industrials": "XLI",
            "Energy": "XLE",
            "Healthcare": "XLV",
            "Communication Services": "XLC",
            "Consumer Defensive": "XLP",
            "Utilities": "XLU",
            "Basic Materials": "XLB",
            "Real Estate": "XLRE",
        },
        description="FMP /profile.sector 字符串 → cockpit 11 GICS sector ETF symbol（T4 SECTOR_CYCLE detector 用，与 SECTOR_ETFS 一一对应）",
    )
    INDEX_ETFS: list[str] = Field(
        default=["SPY", "QQQ", "IWM", "VXX"],
        description="Broad-market index ETFs used in trend scoring; VXX proxies VIX (iPath S&P 500 VIX Short-Term Futures)",
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
            "RISK_ON": 1.25,
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
            "RISK_ON": ["BREAKOUT", "CAPITULATION", "RECLAIM"],
            "CONSTRUCTIVE": ["BREAKOUT", "CAPITULATION"],
            "NEUTRAL": ["CAPITULATION", "RECLAIM"],
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
            "DEFENSIVE": ["BREAKOUT", "CAPITULATION", "EXTENDED"],
            "RISK_OFF": ["BREAKOUT", "CAPITULATION", "RECLAIM", "EARNINGS_DRIFT", "EXTENDED"],
        },
        description="Setup types to avoid for each regime",
    )


SHARED = CockpitSharedParams()
REGIME = CockpitRegimeParams()


class CockpitSetupParams(BaseModel):
    """§2 SETUP — setup type classification, quality thresholds, Ready signal gates."""

    model_config = ConfigDict(frozen=True)

    # ── MA 周期（trend_score 5 阶梯：close>MA10>MA21>MA50>MA150>MA200）──────
    MA_PERIODS: list[int] = Field(
        default=[10, 21, 50, 150, 200],
        description="5 MA periods for trend_score ladder: close>MA10>MA21>MA50>MA150>MA200",
    )

    # ── 成交量状态阈值（vs 20 日均量）──────────────────────────────────────
    VOLUME_MA_PERIOD: int = Field(default=20, description="Rolling period for volume average", ge=5, le=50)
    VOLUME_HIGH_RATIO: float = Field(default=1.2, description="last_volume/avg > this → HIGH", ge=1.0, le=3.0)
    VOLUME_LOW_RATIO: float = Field(default=0.8, description="last_volume/avg < this → LOW", ge=0.1, le=1.0)

    # ── Setup 分类阈值 ────────────────────────────────────────────────────
    EXTENDED_MA50_PCT: float = Field(
        default=15.0,
        description="close > MA50*(1 + this/100) → EXTENDED",
        ge=5.0, le=50.0,
    )
    BREAKOUT_ZONE_PCT: float = Field(
        default=5.0,
        description="close within this% below 20d-high → BREAKOUT zone",
        ge=0.5, le=10.0,
    )
    RECLAIM_LOOKBACK_BARS: int = Field(
        default=10,
        description="Look back N bars to find a close < MA50; if found and current close > MA50 → RECLAIM",
        ge=2, le=30,
    )
    EARNINGS_DRIFT_MAX_DAYS: int = Field(
        default=7,
        description="Earnings in past N days + price above MA21 → EARNINGS_DRIFT",
        ge=1, le=21,
    )

    # ── Setup quality 阈值 ────────────────────────────────────────────────
    QUALITY_A_TREND_MIN: int = Field(default=4, description="Min trend_score for quality A", ge=1, le=5)
    QUALITY_A_RS_MIN: float = Field(default=75.0, description="Min rs_percentile for quality A", ge=1.0, le=100.0)
    QUALITY_B_TREND_MIN: int = Field(default=3, description="Min trend_score for quality B", ge=1, le=5)
    QUALITY_B_RS_MIN: float = Field(default=60.0, description="Min rs_percentile for quality B", ge=1.0, le=100.0)
    QUALITY_C_TREND_MIN: int = Field(default=2, description="Min trend_score for quality C", ge=1, le=5)
    QUALITY_C_RS_MIN: float = Field(default=45.0, description="Min rs_percentile for quality C", ge=1.0, le=100.0)

    # ── RS percentile 计算 ────────────────────────────────────────────────
    RS_LOOKBACK_DAYS: int = Field(
        default=252,
        description="Days of history used for RS return calculation (stock and SPY)",
        ge=20, le=500,
    )
    RS_SPY_FALLBACK_PCT: float = Field(
        default=50.0,
        description="rs_percentile fallback when SPY data unavailable or single-stock watchlist",
        ge=0.0, le=100.0,
    )

    # ── Ready signal 7 条 AND 门 ──────────────────────────────────────────
    READY_TREND_MIN: int = Field(default=4, description="Min trend_score for readySignal", ge=1, le=5)
    READY_RS_MIN: float = Field(default=70.0, description="Min rs_percentile for readySignal", ge=1.0, le=100.0)
    READY_QUALITY_MIN: str = Field(
        default="B",
        description="Min quality for readySignal: 'B'→{A,B}; 'A'→{A}; 'C'→{A,B,C}",
    )
    READY_DIST_MAX_PCT: float = Field(default=3.0, description="Max distanceToEntryPct for readySignal (%)", ge=0.1, le=10.0)
    READY_REWARD_RISK_MIN: float = Field(default=2.0, description="Min rewardRisk for readySignal", ge=1.0, le=10.0)

    # ── Stage 门禁（F216-d2 / D093）─────────────────────────────────────────
    READY_REQUIRE_STAGE2: bool = Field(
        default=True,
        description="If True, readySignal further requires weekly_stage==2 (Stan Weinstein Advancing). NULL/0/1/3/4 → ready=False. Off-switch for debug / pre-cron cold start.",
    )

    # ── Earnings risk 阈值 ────────────────────────────────────────────────
    EARNINGS_DANGER_DAYS: int = Field(default=3, description="Days to next earnings ≤ this → DANGER", ge=1, le=14)
    EARNINGS_CAUTION_DAYS: int = Field(default=10, description="Days to next earnings ≤ this (> DANGER) → CAUTION", ge=2, le=30)

    # ── Entry / Stop 价位计算参数 ─────────────────────────────────────────
    ENTRY_TICK_PCT: float = Field(default=0.1, description="Tick above entry level (%); entry = level*(1+this/100)", ge=0.01, le=1.0)
    PIVOT_LOOKBACK_BARS: int = Field(default=20, description="Bars to look back for 20-day pivot high (BREAKOUT detection)", ge=5, le=60)
    BREAKOUT_STOP_MA50_PCT: float = Field(default=2.0, description="Stop = MA50*(1-this/100) for BREAKOUT setups", ge=0.5, le=10.0)
    RECLAIM_STOP_MA50_PCT: float = Field(default=2.0, description="Stop = MA50*(1-this/100) for RECLAIM setups", ge=0.5, le=10.0)
    EARNINGS_DRIFT_STOP_MA21_PCT: float = Field(default=2.0, description="Stop = MA21*(1-this/100) for EARNINGS_DRIFT setups", ge=0.5, le=10.0)

    # ── CAPITULATION_REVERSAL 7 条 AND 门参数（F217-a / D095）────────────────
    CAPITULATION_DROP_LOOKBACK_MIN_DAYS: int = Field(
        default=5, ge=3, le=15,
        description="条件1：累计跌幅滑动窗最小天数",
    )
    CAPITULATION_DROP_LOOKBACK_MAX_DAYS: int = Field(
        default=10, ge=5, le=20,
        description="条件1：累计跌幅滑动窗最大天数",
    )
    CAPITULATION_DROP_PCT: float = Field(
        default=10.0, ge=5.0, le=30.0,
        description="条件1：累计跌幅阈值（绝对值百分比）",
    )
    CAPITULATION_VOL_Z_MIN: float = Field(
        default=2.5, ge=1.5, le=5.0,
        description="条件2：当日 volume z-score 下限",
    )
    CAPITULATION_ATR_TR_MULTIPLIER: float = Field(
        default=2.0, ge=1.5, le=4.0,
        description="条件3：当日 true_range / ATR14 倍数下限",
    )
    CAPITULATION_CLOSE_UPPER_BIN: float = Field(
        default=0.333, ge=0.1, le=0.5,
        description="条件4：close 在当日 (high-low) 区间内，上方 X 分位起算",
    )
    CAPITULATION_NO_NEW_LOW_LOOKAHEAD_DAYS: int = Field(
        default=2, ge=1, le=5,
        description="条件5：次日不创新低观察窗",
    )
    CAPITULATION_SWING_LOW_LOOKBACK: int = Field(
        default=30, ge=10, le=60,
        description="条件6：swing low 检测窗（bars）",
    )
    CAPITULATION_RS_NO_NEW_LOW_DAYS: int = Field(
        default=5, ge=3, le=15,
        description="条件7：RS line 未创新低观察窗",
    )
    CAPITULATION_STOP_BUFFER_PCT: float = Field(
        default=1.5, ge=0.5, le=5.0,
        description="stop 在当日 low 下方的安全垫（NP3）",
    )

    # ── 数据保留 ──────────────────────────────────────────────────────────
    SETUP_RETENTION_DAYS: int = Field(default=60, description="Days to retain setup snapshots (D062)", ge=7, le=365)

    # ── Volume Accumulation 三件套（F215-b / D087 / D088）────────────────
    VOL_ACC_ZSCORE_WINDOW: int = Field(
        default=50,
        description="Rolling window (bars) for volume z-score; need window+1 bars minimum",
        ge=10, le=200,
    )
    VOL_ACC_OBV_LOOKBACK: int = Field(
        default=20,
        description="Look-back bars for OBV trend comparison (obv[-1] vs obv[-N])",
        ge=5, le=100,
    )
    VOL_ACC_OBV_FLAT_PCT: float = Field(
        default=2.0,
        description="OBV relative change threshold (%); |change| < this → FLAT",
        ge=0.1, le=20.0,
    )
    VOL_ACC_UD_WINDOW: int = Field(
        default=50,
        description="Rolling window (bars) for U/D ratio accumulation",
        ge=10, le=200,
    )
    VOL_ACC_BREAKOUT_Z_MIN: float = Field(
        default=1.5,
        description="BREAKOUT gate: volume_zscore must be >= this; else downgrade to NONE (D088)",
        ge=0.0, le=5.0,
    )
    VOL_ACC_BREAKOUT_UD_MIN: float = Field(
        default=1.2,
        description="BREAKOUT gate: up_down_volume_ratio must be >= this; else downgrade to NONE (D088)",
        ge=0.0, le=10.0,
    )


SETUP = CockpitSetupParams()


class CockpitChartParams(BaseModel):
    """§3 CHART — bars window / MA periods allowlist / ATR period / AVWAP fallback."""

    model_config = ConfigDict(frozen=True)

    # ── Bars 窗口 ────────────────────────────────────────────────────────
    DEFAULT_DAYS: int = Field(default=250, description="Default bars days when client omits ?days", ge=100, le=400)
    MIN_DAYS: int = Field(default=100, description="Lower bound for ?days", ge=20, le=400)
    MAX_DAYS: int = Field(default=400, description="Upper bound for ?days", ge=100, le=1000)

    # ── MA 周期允许范围 ──────────────────────────────────────────────────
    DEFAULT_MAS: list[int] = Field(default=[10, 21, 50, 150, 200], description="Default MA periods returned when ?mas omitted")
    MA_MIN: int = Field(default=5, description="Min single MA period", ge=2, le=100)
    MA_MAX: int = Field(default=250, description="Max single MA period", ge=50, le=500)
    MA_MAX_COUNT: int = Field(default=8, description="Max number of MA series allowed in one request", ge=1, le=20)

    # ── EMA 周期（固定，不接受查询参数）────────────────────────────────────
    DEFAULT_EMAS: list[int] = Field(
        default=[10, 21],
        description="EMA periods always computed and returned alongside MAs; α=2/(period+1), seed=SMA(period)",
    )

    # ── ATR ──────────────────────────────────────────────────────────────
    ATR_PERIOD: int = Field(default=14, description="ATR rolling period", ge=5, le=50)

    # ── AVWAP fallback ────────────────────────────────────────────────────
    AVWAP_FALLBACK_DAYS: int = Field(
        default=0,
        description="If no anchor and no earnings_event, fall back to N days back from latest bar (0 = no fallback, return empty avwap series)",
        ge=0, le=180,
    )


CHART = CockpitChartParams()


class CockpitDecisionParams(BaseModel):
    """§4 DECISION — position sizing, hash, override policy, and fallback values (D070)."""

    model_config = ConfigDict(frozen=True)

    # ── Deterministic hash (D068) ────────────────────────────────────────────
    HASH_DIGEST_LENGTH: int = Field(default=16, description="Hex characters to keep from SHA-256 digest", ge=8, le=64)
    HASH_PRICE_DECIMALS: int = Field(default=2, description="Decimal places for entry/stop in hash preimage", ge=0, le=6)
    HASH_RISK_DECIMALS: int = Field(default=4, description="Decimal places for effective_risk_pct in hash preimage", ge=2, le=8)

    # ── Price output precision ────────────────────────────────────────────────
    PRICE_DECIMAL_PLACES: int = Field(default=2, description="Decimal places for price/value output fields", ge=0, le=6)
    ACCOUNT_RISK_DECIMAL_PLACES: int = Field(default=2, description="Decimal places for accountRiskPct output", ge=0, le=6)

    # ── Override policy ──────────────────────────────────────────────────────
    OVERRIDE_RECOMPUTE_RR: bool = Field(
        default=False,
        description=(
            "When True, recompute rewardRisk from overridden entry/stop. "
            "False (default): preserve setup_snapshots reward_risk regardless of overrides."
        ),
    )

    # ── Fallbacks ────────────────────────────────────────────────────────────
    REGIME_FALLBACK: str = Field(
        default="NEUTRAL",
        description="Regime label used when market_regime_snapshots table is empty",
    )
    DEFAULT_ACCOUNT_SIZE: float = Field(
        default=100000.0,
        description="Account size used when no user_settings row exists (mirrors _DEFAULTS)",
        gt=0,
    )
    DEFAULT_SINGLE_TRADE_RISK_PCT: float = Field(
        default=1.0,
        description="Single-trade risk % used when no user_settings row exists (mirrors _DEFAULTS)",
        ge=0,
        le=5,
    )


DECISION = CockpitDecisionParams()


class CockpitWeeklyParams(BaseModel):
    """§5 WEEKLY — weekly bar aggregation parameters (F216-a / D090)."""

    model_config = ConfigDict(frozen=True)

    DEFAULT_WEEKS: int = Field(default=50, description="Default output weeks for get_weekly_chart", ge=10, le=260)
    WEEKLY_MAS: list[int] = Field(default=[10, 30, 40], description="Weekly SMA periods computed by WeeklyChartService")
    MIN_DAILY_BARS_FOR_WEEKLY: int = Field(default=4, description="Minimum daily bars required before aggregation; below this returns empty result", ge=1, le=20)


WEEKLY = CockpitWeeklyParams()


class CockpitWeeklyStageParams(BaseModel):
    """§6 WEEKLY_STAGE — Stan Weinstein Stage 1-4 classification parameters (F216-b / D091)."""

    model_config = ConfigDict(frozen=True)

    # ── 数据门槛 ──────────────────────────────────────────────────────────
    MIN_WEEKS_FOR_CLASSIFICATION: int = Field(
        default=30, ge=10, le=100,
        description="Min weekly bars required to compute 30wMA and classify stage; below → UNKNOWN",
    )
    SLOPE_LOOKBACK_WEEKS: int = Field(
        default=5, ge=2, le=26,
        description="Window size (weeks) for OLS regression of 30wMA; uses last N+1 points",
    )

    # ── Stage 1（base / 走平）────────────────────────────────────────────
    STAGE1_FLAT_TOL_PCT: float = Field(
        default=2.0, ge=0.1, le=10.0,
        description="|slope_30w| <= this AND price within band → Stage 1",
    )
    STAGE1_PRICE_BAND_PCT: float = Field(
        default=3.0, ge=0.5, le=10.0,
        description="|close - ma30|/ma30 <= this → 价格在 30wMA 附近震荡",
    )

    # ── Stage 2（advancing）──────────────────────────────────────────────
    STAGE2_SLOPE_MIN_PCT: float = Field(
        default=0.5, ge=0.0, le=10.0,
        description="slope_30w > this AND close > 30wMA AND 10wMA>30wMA → Stage 2",
    )

    # ── Stage 3（distribution / topping）────────────────────────────────
    STAGE3_FLAT_TOL_PCT: float = Field(
        default=2.0, ge=0.1, le=10.0,
        description="|slope_30w| <= this AND 反复穿越 30wMA → Stage 3",
    )
    STAGE3_CROSSING_LOOKBACK_WEEKS: int = Field(
        default=10, ge=4, le=26,
        description="Look-back weeks to count close-vs-30wMA crossings",
    )
    STAGE3_MIN_CROSSINGS: int = Field(
        default=3, ge=2, le=10,
        description="Min crossings in lookback to qualify as Stage 3",
    )

    # ── Stage 4（declining）──────────────────────────────────────────────
    STAGE4_SLOPE_MIN_PCT: float = Field(
        default=0.5, ge=0.0, le=10.0,
        description="slope_30w < -this AND close < 30wMA → Stage 4",
    )

    # ── 数据保留 ──────────────────────────────────────────────────────────
    WEEKLY_STAGE_RETENTION_DAYS: int = Field(
        default=60, ge=7, le=365,
        description="Days to retain weekly_stage snapshots (与 SetupSnapshot 对齐)",
    )


WEEKLY_STAGE = CockpitWeeklyStageParams()


class CockpitChartWeeklyParams(BaseModel):
    """§7 CHART_WEEKLY — router-layer validation bounds for GET /chart/{ticker}/weekly (F216-c1)."""

    model_config = ConfigDict(frozen=True)

    MIN_WEEKS: int = Field(default=10, description="Lower bound for ?weeks query param", ge=1, le=50)
    MAX_WEEKS: int = Field(default=WEEKLY.DEFAULT_WEEKS, description="Upper bound for ?weeks; mirrors WEEKLY.DEFAULT_WEEKS (50)", ge=10, le=260)


CHART_WEEKLY = CockpitChartWeeklyParams()
