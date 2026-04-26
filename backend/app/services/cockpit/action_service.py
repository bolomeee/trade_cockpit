"""F207-a: ActionService — rule engine for today's action list."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.external.fmp_client import FmpClient
from app.repositories.earnings_event_repository import EarningsEventRepository
from app.repositories.market_regime_repository import MarketRegimeRepository
from app.repositories.pending_order_repository import PendingOrderRepository
from app.repositories.position_repository import PositionRepository
from app.repositories.setup_snapshot_repository import SetupSnapshotRepository
from app.services.cockpit.last_close_loader import LastCloseLoader
from app.services.cockpit.position_action_rules import compute_next_action

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
APPROACH_TRIGGER_THRESHOLD_PCT = 3.0
EARNINGS_REDUCE_DAYS = 2
REGIME_TIGHTEN_SET = frozenset({"DEFENSIVE", "RISK_OFF"})

ActionType = Literal[
    "raise_stop",
    "cancel_order",
    "reduce_before_earnings",
    "tighten_stop",
    "approaching_trigger",
    "stable_position",
]

_MUST_ACT_PRIORITY: dict[str, int] = {
    "tighten_stop": 0,
    "reduce_before_earnings": 1,
    "raise_stop": 2,
    "cancel_order": 3,
}


class ActionService:
    def __init__(self, db: Session, fmp: FmpClient) -> None:
        self._db = db
        self._positions_repo = PositionRepository(db)
        self._orders_repo = PendingOrderRepository(db)
        self._setup_repo = SetupSnapshotRepository(db)
        self._earnings_repo = EarningsEventRepository(db)
        self._regime_repo = MarketRegimeRepository(db)
        self._last_close_loader = LastCloseLoader(db, fmp)

    def build_today_actions(self) -> dict[str, Any]:
        """Returns {as_of_date, must_act, monitor, no_action} ready to serialize."""
        raise NotImplementedError
