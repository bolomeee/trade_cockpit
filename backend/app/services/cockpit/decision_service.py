"""F203-b2: compute deterministic Decision (entry / stop / position-size) for a ticker."""

from __future__ import annotations

import hashlib
from datetime import date
from math import floor

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.earnings_event import EarningsEvent
from app.models.market_regime_snapshot import MarketRegimeSnapshot
from app.models.setup_snapshot import SetupSnapshot
from app.repositories.user_settings_repository import UserSettingsRepository
from app.schemas.cockpit.decision import DecisionData
from app.services.cockpit.cockpit_params import DECISION, REGIME, SETUP


def _earnings_risk_and_date(db: Session, ticker: str) -> tuple[str | None, date | None]:
    today = date.today()
    row = db.execute(
        select(EarningsEvent)
        .where(EarningsEvent.ticker == ticker)
        .where(EarningsEvent.earnings_date >= today)
        .order_by(EarningsEvent.earnings_date.asc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        return None, None
    days_to = (row.earnings_date - today).days
    if days_to <= SETUP.EARNINGS_DANGER_DAYS:
        risk_level = "DANGER"
    elif days_to <= SETUP.EARNINGS_CAUTION_DAYS:
        risk_level = "CAUTION"
    else:
        risk_level = "SAFE"
    return risk_level, row.earnings_date


def _compute_hash(
    ticker: str, entry: float, stop: float, effective_risk_pct: float, snapshot_date: date
) -> str:
    preimage = (
        f"{ticker}"
        f"|{entry:.{DECISION.HASH_PRICE_DECIMALS}f}"
        f"|{stop:.{DECISION.HASH_PRICE_DECIMALS}f}"
        f"|{effective_risk_pct:.{DECISION.HASH_RISK_DECIMALS}f}"
        f"|{snapshot_date.isoformat()}"
    )
    return hashlib.sha256(preimage.encode()).hexdigest()[: DECISION.HASH_DIGEST_LENGTH]


def compute_decision(
    db: Session,
    ticker: str,
    entry_override: float | None = None,
    stop_override: float | None = None,
    risk_pct_override: float | None = None,
) -> DecisionData:
    """Return DecisionData for ticker.

    Raises:
        LookupError: no setup_snapshot and insufficient overrides to supply entry/stop (→ 404).
        ValueError: computed entry ≤ stop (→ 422).
    """
    ticker = ticker.upper()

    snapshot: SetupSnapshot | None = db.execute(
        select(SetupSnapshot)
        .where(SetupSnapshot.ticker == ticker)
        .order_by(SetupSnapshot.scan_date.desc())
        .limit(1)
    ).scalar_one_or_none()

    # Resolve entry / stop (override wins; fall back to snapshot; None → 404)
    entry_val = entry_override if entry_override is not None else (
        snapshot.entry_price if snapshot is not None else None
    )
    stop_val = stop_override if stop_override is not None else (
        snapshot.stop_price if snapshot is not None else None
    )

    if entry_val is None or stop_val is None:
        raise LookupError(
            f"No setup_snapshot found for '{ticker}' and entry/stop overrides are insufficient"
        )

    entry = float(entry_val)
    stop = float(stop_val)

    if entry <= stop:
        raise ValueError(f"entry ({entry}) must be greater than stop ({stop})")

    # Snapshot metadata (None when no snapshot)
    setup_type = snapshot.setup_type if snapshot else None
    setup_quality = snapshot.setup_quality if snapshot else None
    reward_risk = snapshot.reward_risk if snapshot else None
    snapshot_date = snapshot.scan_date if snapshot else date.today()

    # Regime cap
    regime_row: MarketRegimeSnapshot | None = db.execute(
        select(MarketRegimeSnapshot).order_by(MarketRegimeSnapshot.date.desc()).limit(1)
    ).scalar_one_or_none()
    if regime_row is not None:
        regime_cap = float(regime_row.single_trade_risk_pct)
    else:
        regime_cap = float(REGIME.SINGLE_TRADE_RISK_PCT[DECISION.REGIME_FALLBACK])

    # User settings cap
    user_settings = UserSettingsRepository(db).get_or_default()
    user_cap = float(user_settings["single_trade_risk_pct"])
    account_size = float(user_settings["account_size"])

    # Effective risk pct — override can only narrow, never widen
    caps: list[float] = [regime_cap, user_cap]
    if risk_pct_override is not None:
        caps.append(float(risk_pct_override))
    effective_risk_pct = min(caps)

    # Position sizing
    risk_per_share = round(entry - stop, DECISION.PRICE_DECIMAL_PLACES)

    if effective_risk_pct <= 0:
        suggested_shares = 0
        position_value = 0.0
        account_risk_pct = 0.0
    else:
        suggested_shares = floor(account_size * effective_risk_pct / 100.0 / risk_per_share)
        position_value = round(suggested_shares * entry, DECISION.PRICE_DECIMAL_PLACES)
        account_risk_pct = round(
            (suggested_shares * risk_per_share) / account_size * 100.0,
            DECISION.ACCOUNT_RISK_DECIMAL_PLACES,
        )

    target_2r = round(entry + 2.0 * (entry - stop), DECISION.PRICE_DECIMAL_PLACES)
    target_3r = round(entry + 3.0 * (entry - stop), DECISION.PRICE_DECIMAL_PLACES)

    earnings_risk, earnings_date = _earnings_risk_and_date(db, ticker)
    deterministic_hash = _compute_hash(ticker, entry, stop, effective_risk_pct, snapshot_date)

    return DecisionData(
        ticker=ticker,
        setup_type=setup_type,
        setup_quality=setup_quality,
        entry_price=round(entry, DECISION.PRICE_DECIMAL_PLACES),
        stop_price=round(stop, DECISION.PRICE_DECIMAL_PLACES),
        target_2r=target_2r,
        target_3r=target_3r,
        reward_risk=reward_risk,
        risk_per_share=risk_per_share,
        suggested_shares=suggested_shares,
        position_value=position_value,
        account_risk_pct=account_risk_pct,
        effective_risk_pct=round(effective_risk_pct, DECISION.PRICE_DECIMAL_PLACES),
        regime_cap=round(regime_cap, DECISION.PRICE_DECIMAL_PLACES),
        user_setting_cap=round(user_cap, DECISION.PRICE_DECIMAL_PLACES),
        earnings_risk=earnings_risk,
        earnings_date=earnings_date,
        deterministic_hash=deterministic_hash,
    )
