from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.user_settings import UserSettings

_DEFAULTS: dict = {
    "account_size": 100000.0,
    "max_exposure_pct": 80.0,
    "single_trade_risk_pct": 1.0,
    "default_risk_per_trade_pct": 0.75,
    "base_currency": "USD",
    "updated_at": None,
}


class UserSettingsRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self) -> UserSettings | None:
        """Return id=1 row; None if table is empty (no write)."""
        return self._db.query(UserSettings).filter(UserSettings.id == 1).first()

    def get_or_default(self) -> dict:
        """GET endpoint use: return DB row as dict if exists, else default dict (no write)."""
        row = self.get()
        if row is None:
            return dict(_DEFAULTS)
        return {
            "account_size": row.account_size,
            "max_exposure_pct": row.max_exposure_pct,
            "single_trade_risk_pct": row.single_trade_risk_pct,
            "default_risk_per_trade_pct": row.default_risk_per_trade_pct,
            "base_currency": row.base_currency,
            "updated_at": row.updated_at,
        }

    def upsert(self, patch: dict) -> UserSettings:
        """PUT endpoint use: get or create id=1, apply patch fields, refresh updated_at."""
        row = self.get()
        now = datetime.now(timezone.utc)
        if row is None:
            row = UserSettings(
                id=1,
                account_size=_DEFAULTS["account_size"],
                max_exposure_pct=_DEFAULTS["max_exposure_pct"],
                single_trade_risk_pct=_DEFAULTS["single_trade_risk_pct"],
                default_risk_per_trade_pct=_DEFAULTS["default_risk_per_trade_pct"],
                base_currency=_DEFAULTS["base_currency"],
                updated_at=now,
            )
            self._db.add(row)
        for field, value in patch.items():
            setattr(row, field, value)
        row.updated_at = now
        self._db.commit()
        self._db.refresh(row)
        return row
