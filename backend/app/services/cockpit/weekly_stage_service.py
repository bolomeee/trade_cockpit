"""F216-b: Stan Weinstein Stage 1-4 weekly stage classifier + persistence."""
from __future__ import annotations

import numpy as np

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Stock
from app.repositories.stock_repository import StockRepository
from app.repositories.weekly_stage_repository import WeeklyStageRepository
from app.services.cockpit.cockpit_params import WEEKLY_STAGE
from app.services.cockpit.weekly_chart_service import WeeklyChartService
from app.services.watchlist_service import APIError

# ── Stage integer constants ───────────────────────────────────────────────────
STAGE_UNKNOWN = 0
STAGE_1 = 1
STAGE_2 = 2
STAGE_3 = 3
STAGE_4 = 4


@dataclass
class WeeklyStageResult:
    stage: int                  # 0=UNKNOWN, 1-4
    weekly_close: float | None
    weekly_ma_10: float | None
    weekly_ma_30: float | None
    weekly_ma_40: float | None
    slope_30w: float | None     # %/周，OLS 归一化（NP2）


class WeeklyStageService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._chart = WeeklyChartService(db)
        self._repo = WeeklyStageRepository(db)
        self._stocks = StockRepository(db)

    # ── Public ───────────────────────────────────────────────────────────────

    def classify(
        self,
        weekly_bars: list[dict[str, Any]],
        weekly_ma_10: list[dict[str, Any]],
        weekly_ma_30: list[dict[str, Any]],
        weekly_ma_40: list[dict[str, Any]],
    ) -> WeeklyStageResult:
        """Pure function: classify stage from pre-aggregated weekly bars + MA series.

        Returns WeeklyStageResult with stage=UNKNOWN when data is insufficient.
        Never raises; caller is responsible for supplying valid series dicts.
        """
        if len(weekly_bars) < WEEKLY_STAGE.MIN_WEEKS_FOR_CLASSIFICATION:
            return WeeklyStageResult(
                stage=STAGE_UNKNOWN,
                weekly_close=None,
                weekly_ma_10=None,
                weekly_ma_30=None,
                weekly_ma_40=None,
                slope_30w=None,
            )

        close = float(weekly_bars[-1]["close"])
        ma30 = float(weekly_ma_30[-1]["value"]) if weekly_ma_30 else None
        ma10 = float(weekly_ma_10[-1]["value"]) if weekly_ma_10 else None
        ma40 = float(weekly_ma_40[-1]["value"]) if weekly_ma_40 else None

        if ma30 is None or ma30 == 0:
            return WeeklyStageResult(
                stage=STAGE_UNKNOWN,
                weekly_close=close,
                weekly_ma_10=ma10,
                weekly_ma_30=ma30,
                weekly_ma_40=ma40,
                slope_30w=None,
            )

        slope = self._compute_slope_30w(weekly_ma_30)

        # Priority order: Stage 2 / Stage 4 first (clear trend), then Stage 1, then Stage 3
        stage = self._classify_stage(close, ma10, ma30, slope, weekly_bars, weekly_ma_30)

        return WeeklyStageResult(
            stage=stage,
            weekly_close=close,
            weekly_ma_10=ma10,
            weekly_ma_30=ma30,
            weekly_ma_40=ma40,
            slope_30w=slope,
        )

    def compute_for_ticker(
        self, ticker: str, scan_date: date | None = None
    ) -> "WeeklyStageSnapshot":  # noqa: F821 — avoid circular at module level
        """Compute stage for a single ticker and upsert a snapshot row."""
        from app.models.weekly_stage_snapshot import WeeklyStageSnapshot  # local import avoids circular

        ticker = ticker.strip().upper()
        if self._stocks.get_by_ticker(ticker) is None:
            raise APIError("NOT_FOUND", f"ticker {ticker} not found", 404)

        chart = self._chart.get_weekly_chart(ticker)
        result = self.classify(
            chart["weekly_bars"],
            chart["weekly_mas"].get("10", []),
            chart["weekly_mas"].get("30", []),
            chart["weekly_mas"].get("40", []),
        )

        actual_scan_date = scan_date or self._derive_scan_date(chart["weekly_bars"])
        return self._repo.upsert({
            "ticker": ticker,
            "scan_date": actual_scan_date,
            "stage": result.stage,
            "weekly_close": result.weekly_close,
            "weekly_ma_10": result.weekly_ma_10,
            "weekly_ma_30": result.weekly_ma_30,
            "weekly_ma_40": result.weekly_ma_40,
            "slope_30w": result.slope_30w,
            "computed_at": datetime.now(timezone.utc),
        })

    def compute_and_store_all(
        self, scan_date: date | None = None
    ) -> dict[int, int]:
        """Compute + upsert stage for all active stocks.

        Returns {stage: count} for monitoring/logging.
        """
        active_stocks = self._stocks.list_active()
        counts: dict[int, int] = {STAGE_UNKNOWN: 0, STAGE_1: 0, STAGE_2: 0, STAGE_3: 0, STAGE_4: 0}
        for stock in active_stocks:
            try:
                snapshot = self.compute_for_ticker(stock.ticker, scan_date)
                counts[snapshot.stage] = counts.get(snapshot.stage, 0) + 1
            except Exception:
                counts[STAGE_UNKNOWN] += 1
        return counts

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _compute_slope_30w(self, weekly_ma_30: list[dict[str, Any]]) -> float | None:
        """OLS slope of last N+1 30wMA values, normalised to %/week (NP2 / D092).

        Uses np.polyfit (deg=1). Returns beta/mean_y*100; None if insufficient data.
        """
        n = WEEKLY_STAGE.SLOPE_LOOKBACK_WEEKS
        points = weekly_ma_30[-(n + 1):]
        if len(points) < n + 1:
            return None
        values = [p["value"] for p in points if p.get("value") is not None]
        if len(values) < n + 1:
            return None
        y = np.asarray(values, dtype=float)
        x = np.arange(y.size, dtype=float)
        beta, _intercept = np.polyfit(x, y, 1)
        y_mean = float(y.mean())
        if y_mean == 0:
            return None
        return float(beta / y_mean) * 100

    def _classify_stage(
        self,
        close: float,
        ma10: float | None,
        ma30: float,
        slope: float | None,
        weekly_bars: list[dict[str, Any]],
        ma30_series: list[dict[str, Any]],
    ) -> int:
        """Apply Stage 2/4/1/3 priority rules; returns STAGE_* constant."""
        # Stage 2: rising 30wMA + close > 30wMA (+ 10wMA above 30wMA when available)
        if (
            slope is not None
            and slope > WEEKLY_STAGE.STAGE2_SLOPE_MIN_PCT
            and close > ma30
            and (ma10 is None or ma10 > ma30)
        ):
            return STAGE_2

        # Stage 4: declining 30wMA + close below 30wMA
        if slope is not None and slope < -WEEKLY_STAGE.STAGE4_SLOPE_MIN_PCT and close < ma30:
            return STAGE_4

        # Stage 1: 30wMA flat + price hugging 30wMA
        if (
            slope is not None
            and abs(slope) <= WEEKLY_STAGE.STAGE1_FLAT_TOL_PCT
            and abs(close - ma30) / ma30 <= WEEKLY_STAGE.STAGE1_PRICE_BAND_PCT / 100
        ):
            return STAGE_1

        # Stage 3: 30wMA flat + repeated crossings
        if (
            slope is not None
            and abs(slope) <= WEEKLY_STAGE.STAGE3_FLAT_TOL_PCT
            and self._ma30_crossings_recent(weekly_bars, ma30_series) >= WEEKLY_STAGE.STAGE3_MIN_CROSSINGS
        ):
            return STAGE_3

        return STAGE_UNKNOWN

    def _ma30_crossings_recent(
        self,
        weekly_bars: list[dict[str, Any]],
        ma30_series: list[dict[str, Any]],
    ) -> int:
        """Count close-vs-30wMA sign changes in last STAGE3_CROSSING_LOOKBACK_WEEKS weeks."""
        window = WEEKLY_STAGE.STAGE3_CROSSING_LOOKBACK_WEEKS
        aligned = self._align_by_date(weekly_bars, ma30_series)[-window:]
        crossings = 0
        for i in range(1, len(aligned)):
            prev_diff = aligned[i - 1]["close"] - aligned[i - 1]["ma30"]
            curr_diff = aligned[i]["close"] - aligned[i]["ma30"]
            if prev_diff * curr_diff < 0:  # sign flip = crossing
                crossings += 1
        return crossings

    @staticmethod
    def _align_by_date(
        weekly_bars: list[dict[str, Any]],
        ma30_series: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Inner-join weekly_bars and ma30_series on date; returns merged dicts."""
        ma30_map = {p["date"]: p["value"] for p in ma30_series}
        result = []
        for bar in weekly_bars:
            d = bar["date"]
            if d in ma30_map:
                result.append({"close": bar["close"], "ma30": ma30_map[d]})
        return result

    @staticmethod
    def _derive_scan_date(weekly_bars: list[dict[str, Any]]) -> date:
        """Derive scan_date from weekly_bars: last bar's date (NP4)."""
        if weekly_bars:
            return weekly_bars[-1]["date"]
        return date.today()
