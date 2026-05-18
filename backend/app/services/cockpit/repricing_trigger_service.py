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
        """T1 — F218-d2 实装。当前返回 None（不命中）。"""
        return None

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
