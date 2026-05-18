"""F218-d1: RepricingTriggerService skeleton — 5-class串行 detector 调度 + soft expire.

5 个 detector 的真实实装由后续 sub-sprint 完成：
  - F218-d2 → _detect_earnings_acceleration（T1）
  - F218-d3b → _detect_margin_expansion（T2）
  - F218-d4 → _detect_new_product（T3 D4a）
  - F218-d5 → _detect_sector_cycle（T4）
  - F218-d6b → _detect_balance_inflection（T5）

本 sub-sprint 5 个 _detect_* 均返回 None（不命中），主入口仍可端到端跑通：
  - 既有 active 行 + 当日未命中 → soft expire 翻 false
  - 无既有行 + 不命中 → 无副作用
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.earnings_event_repository import EarningsEventRepository
from app.repositories.repricing_trigger_repository import RepricingTriggerRepository
from app.repositories.stock_repository import StockRepository

logger = logging.getLogger(__name__)

# 5 类 trigger_type 枚举常量（与 DATA-MODEL.md §RepricingTrigger 对齐）
TRIGGER_TYPES = (
    "EARNINGS_ACCEL",
    "MARGIN_EXPANSION",
    "NEW_PRODUCT",
    "SECTOR_CYCLE",
    "BALANCE_INFLECTION",
)

# T1 EARNINGS_ACCEL detector 参数
T1_LOOKBACK_QUARTERS = 6        # 需 Q-3..Q-1 + 上年同期 = 6 季
T1_REQUIRED_QUARTERS = 3        # 检查 YoY 加速的最近季度数
T1_HIGH_CONFIDENCE_YOY = 0.30   # 最近一季 EPS YoY ≥ 30% → confidence=0.8
T1_HIGH_CONFIDENCE_SCORE = 0.8
T1_DEFAULT_CONFIDENCE = 0.5


@dataclass
class DetectorResult:
    """detector 返回类型。命中 → 实例；未命中 → None。"""
    confidence: float          # 0.0–1.0
    evidence: dict[str, Any]   # 按 trigger_type 区分 schema（DATA-MODEL.md §RepricingTrigger evidence_json schema）


class RepricingTriggerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._repo = RepricingTriggerRepository(db)
        self._stocks = StockRepository(db)
        self._earnings = EarningsEventRepository(db)

    # ── Public ────────────────────────────────────────────────────────────────

    def compute_and_store_all_triggers(self, scan_date: date | None = None) -> dict[str, int]:
        """主入口：遍历 active stocks，对每个 ticker 串行跑 5 detector，写入 / soft expire.

        Returns: {trigger_type: hit_count} 用于日志/监控（含 0 命中类型）。
        """
        scan_date = scan_date or datetime.now(timezone.utc).date()
        active_tickers = [s.ticker for s in self._stocks.list_active()]
        hit_counts = {t: 0 for t in TRIGGER_TYPES}

        for ticker in active_tickers:
            for trigger_type, detector_fn in self._detector_map().items():
                try:
                    result = detector_fn(ticker, scan_date)
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "repricing detector failed: ticker=%s type=%s", ticker, trigger_type,
                    )
                    continue

                if result is None:
                    self._repo.soft_expire(ticker, trigger_type, scan_date)
                    continue

                self._repo.upsert({
                    "ticker": ticker,
                    "trigger_type": trigger_type,
                    "detected_date": scan_date,
                    "confidence": result.confidence,
                    "evidence_json": json.dumps(result.evidence),
                    "active": True,
                    "computed_at": datetime.now(timezone.utc),
                })
                hit_counts[trigger_type] += 1

        logger.info("repricing triggers computed: date=%s counts=%s", scan_date, hit_counts)
        return hit_counts

    # ── Detector 占位 ── (d2–d6b 各自实装一个) ────────────────────────────────

    def _detect_earnings_acceleration(
        self, ticker: str, scan_date: date,
    ) -> DetectorResult | None:
        """T1: 最近 3 季度 EPS YoY 增长率严格单调递增 → 触发。

        需要 6 季 actual EPS（最近 3 季 + 上年同期 3 季）；任一季缺失 → return None。
        上年同期 EPS ≤ 0 → 该季 YoY 视为不可计算 → return None（避免负基准除法噪声）。
        revenue_yoy_growth 同步计算用于 evidence；revenue_actual 缺失时该位为 None
        （不影响 EPS 触发判定）。
        """
        rows = self._earnings.get_recent_completed_for_ticker(
            ticker, limit=T1_LOOKBACK_QUARTERS,
        )
        if len(rows) < T1_LOOKBACK_QUARTERS:
            return None

        # rows 按 earnings_date DESC：rows[0] = 最新，rows[5] = 最早
        # 计算最近 3 季 YoY：(Q-1, Q-2, Q-3) 与 (Q-1y, Q-2y, Q-3y) 配对
        recent = rows[:T1_REQUIRED_QUARTERS]    # 索引 0,1,2 = Q-1, Q-2, Q-3
        prior  = rows[T1_REQUIRED_QUARTERS:]    # 索引 3,4,5 = Q-1y, Q-2y, Q-3y

        eps_yoy: list[float] = []
        revenue_yoy: list[float | None] = []
        for cur, prv in zip(recent, prior):
            if prv.eps_actual is None or prv.eps_actual <= 0:
                return None  # 负基准 / 缺数据
            eps_yoy.append(cur.eps_actual / prv.eps_actual - 1.0)

            if (cur.revenue_actual is None or prv.revenue_actual is None
                    or prv.revenue_actual <= 0):
                revenue_yoy.append(None)
            else:
                revenue_yoy.append(cur.revenue_actual / prv.revenue_actual - 1.0)

        # eps_yoy 当前为 [Q-1, Q-2, Q-3]（最新在前）；反转为时间顺序 [Q-3, Q-2, Q-1]
        eps_yoy.reverse()
        revenue_yoy.reverse()

        # 严格单调递增：eps_yoy[0] < eps_yoy[1] < eps_yoy[2]
        if not (eps_yoy[0] < eps_yoy[1] < eps_yoy[2]):
            return None

        # confidence: 最近一季 EPS YoY ≥ 30% → 0.8；否则 0.5
        confidence = (
            T1_HIGH_CONFIDENCE_SCORE
            if eps_yoy[-1] >= T1_HIGH_CONFIDENCE_YOY
            else T1_DEFAULT_CONFIDENCE
        )

        # quarter label 按 earnings_date 派生日历季度 "YYYYQN"；时间顺序 [Q-3, Q-2, Q-1]
        quarters = [_quarter_label(r.earnings_date) for r in reversed(recent)]

        return DetectorResult(
            confidence=confidence,
            evidence={
                "eps_yoy_growth": [round(v, 4) for v in eps_yoy],
                "revenue_yoy_growth": [
                    round(v, 4) if v is not None else None for v in revenue_yoy
                ],
                "quarters": quarters,
            },
        )

    def _detect_margin_expansion(
        self, ticker: str, scan_date: date,
    ) -> DetectorResult | None:
        """T2 — F218-d3b 实装。当前返回 None。"""
        return None

    def _detect_new_product(
        self, ticker: str, scan_date: date,
    ) -> DetectorResult | None:
        """T3 D4a — F218-d4 实装。当前返回 None。"""
        return None

    def _detect_sector_cycle(
        self, ticker: str, scan_date: date,
    ) -> DetectorResult | None:
        """T4 — F218-d5 实装。当前返回 None。"""
        return None

    def _detect_balance_inflection(
        self, ticker: str, scan_date: date,
    ) -> DetectorResult | None:
        """T5 — F218-d6b 实装。当前返回 None。"""
        return None

    # ── Internal ──────────────────────────────────────────────────────────────

    def _detector_map(self) -> dict[str, Any]:
        """trigger_type → detector function. 调度顺序与 TRIGGER_TYPES 一致。"""
        return {
            "EARNINGS_ACCEL":     self._detect_earnings_acceleration,
            "MARGIN_EXPANSION":   self._detect_margin_expansion,
            "NEW_PRODUCT":        self._detect_new_product,
            "SECTOR_CYCLE":       self._detect_sector_cycle,
            "BALANCE_INFLECTION": self._detect_balance_inflection,
        }


def _quarter_label(d: date) -> str:
    """Map a date to calendar-quarter label, e.g. 2026-02-15 → "2026Q1"."""
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"
