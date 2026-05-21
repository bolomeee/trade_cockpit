from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_fmp_client
from app.external.fmp_client import FmpClient
from app.schemas.cockpit.chart import (
    ChartAvwap,
    ChartBarItem,
    ChartSeriesPoint,
    CockpitChartData,
    CockpitChartResponse,
    WeeklyChartData,
    WeeklyChartResponse,
    WeeklyStagePayload,
)
from app.services.cockpit.chart_service import CockpitChartService
from app.services.cockpit.cockpit_params import CHART, CHART_WEEKLY, WEEKLY
from app.services.cockpit.weekly_chart_service import WeeklyChartService
from app.services.cockpit.weekly_stage_service import WeeklyStageService
from app.services.watchlist_service import APIError

router = APIRouter(prefix="/chart", tags=["cockpit-chart"])


def _get_service(
    db: Session = Depends(get_db),
    fmp: FmpClient = Depends(get_fmp_client),
) -> CockpitChartService:
    return CockpitChartService(db, fmp)


def _get_weekly_chart_service(
    db: Session = Depends(get_db),
    fmp: FmpClient = Depends(get_fmp_client),
) -> WeeklyChartService:
    return WeeklyChartService(db, fmp)


def _get_weekly_stage_service(db: Session = Depends(get_db)) -> WeeklyStageService:
    return WeeklyStageService(db)


@router.get("/{ticker}", response_model=CockpitChartResponse)
def get_cockpit_chart(
    ticker: str,
    mas: str = Query(default=",".join(str(p) for p in CHART.DEFAULT_MAS)),
    days: int = Query(default=CHART.DEFAULT_DAYS),
    anchor: str | None = Query(default=None),
    service: CockpitChartService = Depends(_get_service),
) -> CockpitChartResponse:
    # ── Validate days ────────────────────────────────────────────────────
    if not (CHART.MIN_DAYS <= days <= CHART.MAX_DAYS):
        raise APIError(
            "VALIDATION_ERROR",
            f"days must be between {CHART.MIN_DAYS} and {CHART.MAX_DAYS}",
            422,
        )

    # ── Validate and parse mas ───────────────────────────────────────────
    ma_periods: list[int] = []
    if mas.strip():
        raw_parts = [p.strip() for p in mas.split(",") if p.strip()]
        if len(raw_parts) > CHART.MA_MAX_COUNT:
            raise APIError(
                "VALIDATION_ERROR",
                f"Too many MA periods (max {CHART.MA_MAX_COUNT})",
                422,
            )
        for part in raw_parts:
            try:
                period = int(part)
            except ValueError:
                raise APIError("VALIDATION_ERROR", f"Invalid MA period: {part!r}", 422)
            if not (CHART.MA_MIN <= period <= CHART.MA_MAX):
                raise APIError(
                    "VALIDATION_ERROR",
                    f"MA period {period} out of range [{CHART.MA_MIN}, {CHART.MA_MAX}]",
                    422,
                )
            ma_periods.append(period)

    # ── Validate anchor ──────────────────────────────────────────────────
    parsed_anchor: date | None = None
    if anchor is not None:
        try:
            parsed_anchor = date.fromisoformat(anchor)
        except ValueError:
            raise APIError("VALIDATION_ERROR", f"anchor must be ISO date (YYYY-MM-DD): {anchor!r}", 422)

    # ── Call service ─────────────────────────────────────────────────────
    result = service.get_chart(
        ticker=ticker,
        mas=ma_periods if ma_periods else None,
        days=days,
        anchor=parsed_anchor,
    )

    bars = [ChartBarItem.model_validate(b) for b in result["bars"]]
    mas_out: dict[str, list[ChartSeriesPoint]] = {
        k: [ChartSeriesPoint.model_validate(p) for p in v]
        for k, v in result["mas"].items()
    }
    emas_out: dict[str, list[ChartSeriesPoint]] = {
        k: [ChartSeriesPoint.model_validate(p) for p in v]
        for k, v in result["emas"].items()
    }
    atr_out = [ChartSeriesPoint.model_validate(p) for p in result["atr"]]
    avwap_raw = result["avwap"]
    avwap_out = ChartAvwap(
        anchor=avwap_raw["anchor"],
        series=[ChartSeriesPoint.model_validate(p) for p in avwap_raw["series"]],
    )

    data = CockpitChartData(
        ticker=result["ticker"],
        bars=bars,
        mas=mas_out,
        emas=emas_out,
        atr=atr_out,
        avwap=avwap_out,
    )
    return CockpitChartResponse(data=data)


@router.get("/{ticker}/weekly", response_model=WeeklyChartResponse)
def get_cockpit_weekly_chart(
    ticker: str,
    weeks: int = Query(default=WEEKLY.DEFAULT_WEEKS),
    chart_svc: WeeklyChartService = Depends(_get_weekly_chart_service),
    stage_svc: WeeklyStageService = Depends(_get_weekly_stage_service),
) -> WeeklyChartResponse:
    if not (CHART_WEEKLY.MIN_WEEKS <= weeks <= CHART_WEEKLY.MAX_WEEKS):
        raise APIError(
            "VALIDATION_ERROR",
            f"weeks must be between {CHART_WEEKLY.MIN_WEEKS} and {CHART_WEEKLY.MAX_WEEKS}",
            422,
        )

    chart = chart_svc.get_weekly_chart(ticker=ticker, weeks=weeks)

    result = stage_svc.classify(
        chart["weekly_bars"],
        chart["weekly_mas"].get("10", []),
        chart["weekly_mas"].get("30", []),
        chart["weekly_mas"].get("40", []),
    )

    scan_date = chart["weekly_bars"][-1]["date"] if chart["weekly_bars"] else None

    stage_payload = WeeklyStagePayload(
        stage=result.stage,
        weekly_close=result.weekly_close,
        weekly_ma_10=result.weekly_ma_10,
        weekly_ma_30=result.weekly_ma_30,
        weekly_ma_40=result.weekly_ma_40,
        slope_30w=result.slope_30w,
        scan_date=scan_date,
    )

    bars = [ChartBarItem.model_validate(b) for b in chart["weekly_bars"]]
    mas_out = {
        k: [ChartSeriesPoint.model_validate(p) for p in v]
        for k, v in chart["weekly_mas"].items()
    }

    data = WeeklyChartData(
        ticker=ticker.upper(),
        weekly_bars=bars,
        weekly_mas=mas_out,
        stage=stage_payload,
    )
    return WeeklyChartResponse(data=data)
