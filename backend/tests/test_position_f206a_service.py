"""F206-a §C: unit tests for position_action_rules, position_sizer, and service enrichment."""
from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

from app.models.position import Position
from app.services.cockpit.position_action_rules import compute_next_action
from app.services.cockpit.position_sizer import compute_shares
from app.services.cockpit.position_service import PositionService


# ============================================================
# compute_next_action (4 branches)
# ============================================================

def test_next_action_exit_when_close_at_stop():
    result = compute_next_action(
        last_close=140.0, entry_price=150.0, stop_price=140.0, days_until_earnings=None
    )
    assert result == "exit"


def test_next_action_exit_when_close_below_stop():
    result = compute_next_action(
        last_close=135.0, entry_price=150.0, stop_price=140.0, days_until_earnings=None
    )
    assert result == "exit"


def test_next_action_reduce_earnings_within_2_days():
    result = compute_next_action(
        last_close=160.0, entry_price=150.0, stop_price=140.0, days_until_earnings=2
    )
    assert result == "reduce"


def test_next_action_raise_stop_at_2r():
    # r = (170-150)/(150-140) = 20/10 = 2.0; stop < entry → raise_stop
    result = compute_next_action(
        last_close=170.0, entry_price=150.0, stop_price=140.0, days_until_earnings=None
    )
    assert result == "raise_stop"


def test_next_action_hold_default():
    # r ~= 1.5, not yet 2r, no earnings near
    result = compute_next_action(
        last_close=165.0, entry_price=150.0, stop_price=140.0, days_until_earnings=10
    )
    assert result == "hold"


def test_next_action_hold_when_last_close_none():
    result = compute_next_action(
        last_close=None, entry_price=150.0, stop_price=140.0, days_until_earnings=None
    )
    assert result == "hold"


# ============================================================
# compute_shares (edge cases)
# ============================================================

def test_compute_shares_normal():
    # account=100_000, risk=1%, entry=150, stop=140 → 100_000*0.01/(150-140) = 100
    shares = compute_shares(account_size=100_000, risk_pct=1.0, entry=150.0, stop=140.0)
    assert shares == 100


def test_compute_shares_entry_equals_stop():
    shares = compute_shares(account_size=100_000, risk_pct=1.0, entry=140.0, stop=140.0)
    assert shares == 0


def test_compute_shares_risk_zero():
    shares = compute_shares(account_size=100_000, risk_pct=0.0, entry=150.0, stop=140.0)
    assert shares == 0


# ============================================================
# PositionService._enrich: last_close=None → computed fields are null
# ============================================================

def _make_position_row(**overrides) -> Position:
    row = Position()
    row.id = overrides.get("id", 1)
    row.ticker = overrides.get("ticker", "AAPL")
    row.entry_price = overrides.get("entry_price", 150.0)
    row.entry_date = overrides.get("entry_date", date(2026, 4, 1))
    row.shares = overrides.get("shares", 100)
    row.stop_price = overrides.get("stop_price", 140.0)
    row.target_2r = overrides.get("target_2r", None)
    row.target_3r = overrides.get("target_3r", None)
    row.setup_type = overrides.get("setup_type", None)
    row.notes = overrides.get("notes", None)
    row.status = overrides.get("status", "OPEN")
    row.closed_at = overrides.get("closed_at", None)
    row.close_price = overrides.get("close_price", None)
    row.created_at = overrides.get("created_at", datetime.now(timezone.utc))
    row.updated_at = overrides.get("updated_at", datetime.now(timezone.utc))
    return row


def _make_service(db=None, fmp=None) -> PositionService:
    db = db or MagicMock()
    fmp = fmp or MagicMock()
    svc = PositionService.__new__(PositionService)
    svc._db = db
    svc._fmp = fmp
    svc._repo = MagicMock()
    svc._pending_repo = MagicMock()
    svc._settings_repo = MagicMock()
    svc._earnings_repo = MagicMock()
    svc._setup_repo = MagicMock()
    svc._setup_repo.get_latest_for_tickers.return_value = []
    svc._loader = MagicMock()
    # default: no settings row
    svc._settings_repo.get_or_default.return_value = {
        "account_size": 100_000.0,
        "default_risk_per_trade_pct": 1.0,
        "single_trade_risk_pct": 1.0,
        "max_exposure_pct": 80.0,
        "base_currency": "USD",
        "updated_at": None,
    }
    return svc


def test_enrich_last_close_none_gives_null_computed_fields():
    svc = _make_service()
    row = _make_position_row()
    item = svc._enrich(row, last_close=None, earnings_event=None, include_recommended=False)

    assert item.last_close is None
    assert item.r_multiple is None
    assert item.unrealized_pl is None
    assert item.position_value is None
    assert item.next_action == "hold"


def test_enrich_fmp_failure_does_not_propagate(db_session):
    """FMP failure for a non-watchlist ticker returns None, does not raise."""
    from app.services.cockpit.last_close_loader import LastCloseLoader

    fmp = MagicMock()
    fmp.get_daily_bars.side_effect = Exception("network error")

    loader = LastCloseLoader(db=db_session, fmp=fmp)
    closes = loader.load(["OTC_TICKER"])
    assert closes["OTC_TICKER"] is None


def test_create_position_response_has_recommended_shares(db_session):
    """POST response must include recommendedShares."""
    from app.schemas.cockpit.position import PositionCreate

    svc = _make_service(db=db_session)
    svc._settings_repo.get_or_default.return_value = {
        "account_size": 100_000.0,
        "default_risk_per_trade_pct": 1.0,
        "single_trade_risk_pct": 1.0,
        "max_exposure_pct": 80.0,
        "base_currency": "USD",
        "updated_at": None,
    }
    # Stub repo.create to return a Position row
    created_row = _make_position_row(ticker="AAPL", entry_price=150.0, stop_price=140.0, shares=100)
    svc._repo.create.return_value = created_row
    svc._earnings_repo.get_next_earnings.return_value = None

    # Stub _loader.load to return None (no daily_bars for AAPL in test)
    svc._loader.load.return_value = {"AAPL": None}

    payload = PositionCreate(
        ticker="AAPL",
        entryPrice=150.0,
        entryDate=date(2026, 4, 1),
        shares=100,
        stopPrice=140.0,
    )
    item = svc.create_position(payload)

    # recommendedShares = floor(100_000 * 1.0/100 / (150-140)) = 100
    assert item.recommended_shares == 100
