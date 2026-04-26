"""F207-a: unit tests for ActionService rule engine."""
from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.models.earnings_event import EarningsEvent
from app.models.market_regime_snapshot import MarketRegimeSnapshot
from app.models.pending_order import PendingOrder
from app.models.position import Position
from app.models.setup_snapshot import SetupSnapshot
from app.services.cockpit.action_service import (
    ActionService,
    _MUST_ACT_PRIORITY,
    _classify_pending_order,
    _classify_position,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _pos(**kw) -> Position:
    row = Position()
    row.id = kw.get("id", 1)
    row.ticker = kw.get("ticker", "AAPL")
    row.entry_price = kw.get("entry_price", 150.0)
    row.entry_date = kw.get("entry_date", date(2026, 1, 1))
    row.shares = kw.get("shares", 100)
    row.stop_price = kw.get("stop_price", 140.0)
    row.status = kw.get("status", "OPEN")
    row.target_2r = None
    row.target_3r = None
    row.setup_type = None
    row.notes = None
    row.closed_at = None
    row.close_price = None
    row.created_at = datetime.now(timezone.utc)
    row.updated_at = datetime.now(timezone.utc)
    return row


def _order(**kw) -> PendingOrder:
    row = PendingOrder()
    row.id = kw.get("id", 1)
    row.ticker = kw.get("ticker", "NVDA")
    row.entry_price = kw.get("entry_price", 180.0)
    row.stop_price = kw.get("stop_price", 170.0)
    row.shares = kw.get("shares", 50)
    row.setup_type = kw.get("setup_type", "BREAKOUT")
    row.status = kw.get("status", "ACTIVE")
    row.target_2r = None
    row.target_3r = None
    row.expiration_date = None
    row.notes = None
    row.created_at = datetime.now(timezone.utc)
    row.updated_at = datetime.now(timezone.utc)
    return row


def _earnings(ticker: str, days_from_now: int) -> EarningsEvent:
    ev = EarningsEvent()
    ev.id = 1
    ev.ticker = ticker
    ev.earnings_date = date.today().__class__.fromordinal(
        date.today().toordinal() + days_from_now
    )
    return ev


def _setup_snapshot(ticker: str, setup_type: str, scan_date: date | None = None) -> SetupSnapshot:
    ss = SetupSnapshot()
    ss.id = 1
    ss.ticker = ticker
    ss.setup_type = setup_type
    ss.scan_date = scan_date or date.today()
    ss.suggested_action = None
    return ss


def _regime(regime: str) -> MarketRegimeSnapshot:
    r = MarketRegimeSnapshot()
    r.id = 1
    r.regime = regime
    r.recorded_date = date.today()
    return r


def _make_svc_stub(
    positions=None,
    orders=None,
    last_close_map=None,
    setups=None,
    earnings_map=None,
    regime_row=None,
) -> ActionService:
    """Build an ActionService with all repos stubbed."""
    svc = ActionService.__new__(ActionService)
    svc._positions_repo = MagicMock()
    svc._positions_repo.list_by_status.return_value = positions or []
    svc._orders_repo = MagicMock()
    svc._orders_repo.list_by_status.return_value = orders or []
    svc._setup_repo = MagicMock()
    svc._setup_repo.get_latest_for_tickers.return_value = setups or []
    svc._earnings_repo = MagicMock()
    if earnings_map is not None:
        svc._earnings_repo.get_next_earnings.side_effect = lambda t, _d: earnings_map.get(t)
    else:
        svc._earnings_repo.get_next_earnings.return_value = None
    svc._regime_repo = MagicMock()
    svc._regime_repo.get_latest.return_value = regime_row
    svc._last_close_loader = MagicMock()
    svc._last_close_loader.load.return_value = last_close_map or {}
    return svc


# ── U1: empty DB → all lists empty ────────────────────────────────────────────

def test_u1_empty_db():
    svc = _make_svc_stub()
    result = svc.build_today_actions()
    assert result["must_act"] == []
    assert result["monitor"] == []
    assert result["no_action"] == []
    assert result["as_of_date"] == date.today()


# ── U2: 1 OPEN position rule=hold, no regime → no_action stable_position ──────

def test_u2_stable_position_no_regime():
    p = _pos(entry_price=150.0, stop_price=140.0)
    action_type, rationale, refs, bucket = _classify_position(
        pos=p, last_close=155.0, earnings_event=None, regime=None
    )
    assert action_type == "stable_position"
    assert bucket == "no_action"
    assert rationale == "Trend intact, no rule change"
    assert refs["positionId"] == p.id


# ── U3: stop already breached → must_act raise_stop ───────────────────────────

def test_u3_stop_breached():
    p = _pos(entry_price=150.0, stop_price=140.0)
    action_type, rationale, refs, bucket = _classify_position(
        pos=p, last_close=138.0, earnings_event=None, regime=None
    )
    assert action_type == "raise_stop"
    assert bucket == "must_act"
    assert "stop already breached" in rationale
    assert refs["lastClose"] == 138.0
    assert refs["currentStop"] == 140.0


def test_u3_stop_exactly_at_breached():
    p = _pos(entry_price=150.0, stop_price=140.0)
    action_type, _r, _refs, bucket = _classify_position(
        pos=p, last_close=140.0, earnings_event=None, regime=None
    )
    assert action_type == "raise_stop"
    assert bucket == "must_act"


# ── U4: regime=DEFENSIVE + stable position → must_act tighten_stop ─────────────

def test_u4_regime_defensive_upgrades_stable():
    p = _pos(entry_price=150.0, stop_price=140.0)
    action_type, rationale, refs, bucket = _classify_position(
        pos=p, last_close=155.0, earnings_event=None, regime="DEFENSIVE"
    )
    assert action_type == "tighten_stop"
    assert bucket == "must_act"
    assert "DEFENSIVE" in rationale
    assert refs["regime"] == "DEFENSIVE"


def test_u4_regime_risk_off_upgrades_stable():
    p = _pos(entry_price=150.0, stop_price=140.0)
    action_type, _r, _refs, bucket = _classify_position(
        pos=p, last_close=155.0, earnings_event=None, regime="RISK_OFF"
    )
    assert action_type == "tighten_stop"
    assert bucket == "must_act"


# ── U5: regime=CONSTRUCTIVE + R=2.5 position → must_act raise_stop ─────────────

def test_u5_raise_stop_r_multiple():
    # entry=150, stop=140, risk=10, last_close=175 → R=(175-150)/10=2.5
    p = _pos(entry_price=150.0, stop_price=140.0)
    action_type, rationale, refs, bucket = _classify_position(
        pos=p, last_close=175.0, earnings_event=None, regime="CONSTRUCTIVE"
    )
    assert action_type == "raise_stop"
    assert bucket == "must_act"
    assert "R-multiple" in rationale
    assert "2.50" in rationale
    assert refs["rMultiple"] == 2.5


# ── U6: earnings in 1d → must_act reduce_before_earnings (no regime) ──────────

def test_u6_earnings_in_1d():
    p = _pos(entry_price=150.0, stop_price=140.0)
    ev = _earnings("AAPL", 1)
    action_type, rationale, refs, bucket = _classify_position(
        pos=p, last_close=155.0, earnings_event=ev, regime=None
    )
    assert action_type == "reduce_before_earnings"
    assert bucket == "must_act"
    assert "1 day(s)" in rationale
    assert refs["daysUntilEarnings"] == 1


# ── U7: earnings in 2d + regime=DEFENSIVE → tighten_stop wins ─────────────────

def test_u7_regime_priority_over_earnings():
    p = _pos(entry_price=150.0, stop_price=140.0)
    ev = _earnings("AAPL", 2)
    action_type, _r, refs, bucket = _classify_position(
        pos=p, last_close=155.0, earnings_event=ev, regime="DEFENSIVE"
    )
    # regime priority 2 < earnings priority 3 → tighten_stop wins
    assert action_type == "tighten_stop"
    assert bucket == "must_act"


# ── U8: pending_order distance=2% → monitor approaching_trigger ───────────────

def test_u8_approaching_trigger():
    # last_close = entry × 0.98 → distance ≈ -2%
    o = _order(entry_price=100.0)
    result = _classify_pending_order(order=o, last_close=98.0, setup=None)
    assert result is not None
    action_type, rationale, refs, bucket = result
    assert action_type == "approaching_trigger"
    assert bucket == "monitor"
    assert "(-2.00%)" in rationale
    assert refs["distancePct"] == -2.0


# ── U9: pending_order with BROKEN setup → must_act cancel_order ───────────────

def test_u9_cancel_broken_setup():
    o = _order(ticker="MSFT")
    ss = _setup_snapshot("MSFT", "BROKEN", date(2026, 4, 20))
    result = _classify_pending_order(order=o, last_close=95.0, setup=ss)
    assert result is not None
    action_type, rationale, refs, bucket = result
    assert action_type == "cancel_order"
    assert bucket == "must_act"
    assert "BROKEN" in rationale
    assert "2026-04-20" in rationale
    assert refs["orderId"] == o.id


# ── U10: pending_order distance=10% → not in any list ────────────────────────

def test_u10_far_away_order_not_shown():
    # last_close = entry × 0.90 → distance = -10%
    o = _order(entry_price=100.0)
    result = _classify_pending_order(order=o, last_close=90.0, setup=None)
    assert result is None


# ── U11: must_act sorting ──────────────────────────────────────────────────────
# regime=DEFENSIVE overrides reduce/raise_stop for non-breached positions, so
# all 4 action types can't co-exist via build_today_actions with a single regime.
# Test the sort key directly using _MUST_ACT_PRIORITY.

def test_u11_must_act_sort_key_priority():
    items = [
        {"ticker": "AAPL", "action_type": "raise_stop", "rationale": "", "refs": {}},
        {"ticker": "GOOG", "action_type": "cancel_order", "rationale": "", "refs": {}},
        {"ticker": "MSFT", "action_type": "reduce_before_earnings", "rationale": "", "refs": {}},
        {"ticker": "TSLA", "action_type": "tighten_stop", "rationale": "", "refs": {}},
    ]
    items.sort(key=lambda x: (_MUST_ACT_PRIORITY.get(x["action_type"], 99), x["ticker"]))
    must_types = [x["action_type"] for x in items]
    assert must_types == ["tighten_stop", "reduce_before_earnings", "raise_stop", "cancel_order"]


def test_u11_same_action_type_sorted_by_ticker():
    # Two raise_stop items: TSLA before AAPL alphabetically reversed
    p_aapl = _pos(id=1, ticker="AAPL", entry_price=150.0, stop_price=140.0)
    p_tsla = _pos(id=2, ticker="TSLA", entry_price=300.0, stop_price=270.0)
    svc = _make_svc_stub(
        positions=[p_tsla, p_aapl],  # intentional reverse order
        last_close_map={"AAPL": 138.0, "TSLA": 265.0},  # both stop breached
        regime_row=None,
    )
    result = svc.build_today_actions()
    tickers = [x["ticker"] for x in result["must_act"]]
    assert tickers == ["AAPL", "TSLA"]  # alphabetical within same action type


# ── U12: last_close=None pending_order → not in monitor ───────────────────────

def test_u12_last_close_none_order_not_in_monitor():
    o = _order(entry_price=100.0)
    result = _classify_pending_order(order=o, last_close=None, setup=None)
    assert result is None


# ── U13: no MarketRegimeSnapshot → no error, no tighten_stop ──────────────────

def test_u13_no_regime_no_tighten_stop():
    positions = [_pos(entry_price=150.0, stop_price=140.0)]
    svc = _make_svc_stub(
        positions=positions,
        last_close_map={"AAPL": 155.0},
        regime_row=None,
    )
    result = svc.build_today_actions()
    action_types = [x["action_type"] for x in result["must_act"]]
    assert "tighten_stop" not in action_types
    assert len(result["no_action"]) == 1
    assert result["no_action"][0]["action_type"] == "stable_position"
