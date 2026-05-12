"""F207-a: ActionService — rule engine for today's action list."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.external.fmp_client import FmpClient
from app.models.earnings_event import EarningsEvent
from app.models.market_regime_snapshot import MarketRegimeSnapshot
from app.models.pending_order import PendingOrder
from app.models.position import Position
from app.models.setup_snapshot import SetupSnapshot
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

_ActionTuple = tuple[str, str, dict[str, Any], str]  # (action_type, rationale, refs, bucket)


def _classify_position(
    pos: Position,
    last_close: float | None,
    earnings_event: EarningsEvent | None,
    regime: str | None,
) -> _ActionTuple:
    """Classify a single OPEN position into an action bucket (first match wins).

    Returns (action_type, rationale, refs, bucket) where bucket is "must_act" or "no_action".
    """
    today = date.today()

    # Derived values
    days_until_earnings: int | None = None
    if earnings_event is not None:
        days_until_earnings = (earnings_event.earnings_date - today).days

    rule = compute_next_action(
        last_close=last_close,
        entry_price=pos.entry_price,
        stop_price=pos.stop_price,
        days_until_earnings=days_until_earnings,
    )

    # Priority 1: stop already breached (last_close <= stop_price)
    # §7 Q7: individual hard signal trumps global regime signal
    if last_close is not None and last_close <= pos.stop_price:
        rationale = (
            f"Last close {last_close} <= stop {pos.stop_price}"
            " — stop already breached, immediate review"
        )
        refs: dict[str, Any] = {
            "positionId": pos.id,
            "currentStop": pos.stop_price,
            "lastClose": last_close,
        }
        return ("raise_stop", rationale, refs, "must_act")

    # Priority 2: adverse regime — tighten stops across all open positions
    if regime is not None and regime in REGIME_TIGHTEN_SET:
        rationale = f"Regime turned {regime}; tighten stops across all open positions"
        refs = {"positionId": pos.id, "regime": regime}
        return ("tighten_stop", rationale, refs, "must_act")

    # Priority 3: earnings within threshold days
    if rule == "reduce" and days_until_earnings is not None and earnings_event is not None:
        rationale = (
            f"Earnings in {days_until_earnings} day(s)"
            f" ({earnings_event.earnings_date}); reduce per playbook"
        )
        refs = {
            "positionId": pos.id,
            "earningsDate": str(earnings_event.earnings_date),
            "daysUntilEarnings": days_until_earnings,
        }
        return ("reduce_before_earnings", rationale, refs, "must_act")

    # Priority 4: R-multiple criterion met — consider tightening stop
    if rule == "raise_stop" and last_close is not None:
        risk = pos.entry_price - pos.stop_price
        r_multiple = round((last_close - pos.entry_price) / risk, 2) if risk > 0 else 0.0
        rationale = (
            f"R-multiple {r_multiple:.2f}; stop {pos.stop_price}"
            f" below entry {pos.entry_price} — consider tightening"
        )
        refs = {
            "positionId": pos.id,
            "currentStop": pos.stop_price,
            "rMultiple": r_multiple,
        }
        return ("raise_stop", rationale, refs, "must_act")

    # Priority 5: all clear
    return ("stable_position", "Trend intact, no rule change", {"positionId": pos.id}, "no_action")


def _classify_pending_order(
    order: PendingOrder,
    last_close: float | None,
    setup: SetupSnapshot | None,
) -> _ActionTuple | None:
    """Classify a single ACTIVE pending order.

    Returns (action_type, rationale, refs, bucket) or None if order should not be shown.
    """
    # Priority 1: underlying setup BROKEN
    if setup is not None and setup.setup_type == "BROKEN":
        snapshot_date = str(setup.scan_date)
        rationale = f"Setup BROKEN as of {snapshot_date}; cancel pending order"
        refs: dict[str, Any] = {"orderId": order.id, "setupSnapshotDate": snapshot_date}
        return ("cancel_order", rationale, refs, "must_act")

    # Priority 2: approaching trigger (distance ≤ threshold and not yet triggered)
    if last_close is not None and last_close < order.entry_price:
        distance_pct = (last_close - order.entry_price) / order.entry_price * 100
        if distance_pct >= -APPROACH_TRIGGER_THRESHOLD_PCT:
            rationale = (
                f"Pending order trigger at {order.entry_price};"
                f" current {last_close} ({distance_pct:+.2f}%)"
            )
            refs = {
                "orderId": order.id,
                "entry": order.entry_price,
                "lastClose": last_close,
                "distancePct": round(distance_pct, 2),
            }
            return ("approaching_trigger", rationale, refs, "monitor")

    # Priority 3: too far or last_close unknown — do not display
    return None


def _make_item(ticker: str, action_type: str, rationale: str, refs: dict[str, Any]) -> dict[str, Any]:
    return {"ticker": ticker, "action_type": action_type, "rationale": rationale, "refs": refs}


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
        today = date.today()

        # ── Load raw data ─────────────────────────────────────────────────────
        positions = self._positions_repo.list_by_status("open")
        orders = self._orders_repo.list_by_status("ACTIVE")

        tickers: list[str] = list({p.ticker for p in positions} | {o.ticker for o in orders})

        last_close_map: dict[str, float | None] = (
            self._last_close_loader.load(tickers) if tickers else {}
        )

        setup_list = self._setup_repo.get_latest_for_tickers(tickers) if tickers else []
        setup_map: dict[str, SetupSnapshot] = {s.ticker: s for s in setup_list}

        earnings_map: dict[str, EarningsEvent | None] = {
            p.ticker: self._earnings_repo.get_next_earnings(p.ticker, today)
            for p in positions
        }

        regime_row: MarketRegimeSnapshot | None = self._regime_repo.get_latest()
        if regime_row is None:
            logger.warning("No MarketRegimeSnapshot found; skipping tighten_stop judgement")
        regime: str | None = regime_row.regime if regime_row is not None else None

        # ── Classify ──────────────────────────────────────────────────────────
        must_act: list[dict[str, Any]] = []
        monitor: list[dict[str, Any]] = []
        no_action: list[dict[str, Any]] = []

        for pos in positions:
            action_type, rationale, refs, bucket = _classify_position(
                pos,
                last_close_map.get(pos.ticker),
                earnings_map.get(pos.ticker),
                regime,
            )
            item = _make_item(pos.ticker, action_type, rationale, refs)
            if bucket == "must_act":
                must_act.append(item)
            else:
                no_action.append(item)

        for order in orders:
            result = _classify_pending_order(
                order,
                last_close_map.get(order.ticker),
                setup_map.get(order.ticker),
            )
            if result is None:
                continue
            action_type, rationale, refs, bucket = result
            item = _make_item(order.ticker, action_type, rationale, refs)
            if bucket == "must_act":
                must_act.append(item)
            else:
                monitor.append(item)

        # ── Sort ──────────────────────────────────────────────────────────────
        must_act.sort(key=lambda x: (_MUST_ACT_PRIORITY.get(x["action_type"], 99), x["ticker"]))
        monitor.sort(key=lambda x: x["ticker"])
        no_action.sort(key=lambda x: x["ticker"])

        return {
            "as_of_date": today,
            "must_act": must_act,
            "monitor": monitor,
            "no_action": no_action,
        }
