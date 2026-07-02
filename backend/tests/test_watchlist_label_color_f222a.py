"""F222-a: Tests for Stock.label_color — alembic 026 + GET /api/signals read path.

Sprint Contract standards covered:
  #1 alembic upgrade head → stocks.label_color column exists
  #2 alembic downgrade -1 → stocks.label_color column gone
  #3 upgrade → downgrade → upgrade three-step cycle runs clean
  #4 GET /api/signals: stock without label_color set → labelColor is null
  #5 GET /api/signals: stock with label_color="red" in DB → labelColor == "red"
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.models import DailyBar, Stock
from app.services.signal_service import SignalService


@pytest.fixture()
def alembic_db(tmp_path: Path):
    """Fresh SQLite DB via alembic upgrade head."""
    db_path = tmp_path / "test_label_color.db"
    cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")
    return str(db_path)


class TestAlembic026:
    def test_s1_upgrade_creates_column(self, alembic_db: str) -> None:
        engine = create_engine(f"sqlite:///{alembic_db}")
        cols = {c["name"] for c in inspect(engine).get_columns("stocks")}
        assert "label_color" in cols

    def test_s2_downgrade_removes_column(self, alembic_db: str) -> None:
        cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{alembic_db}")
        command.downgrade(cfg, "-1")
        engine = create_engine(f"sqlite:///{alembic_db}")
        cols = {c["name"] for c in inspect(engine).get_columns("stocks")}
        assert "label_color" not in cols

    def test_s3_upgrade_downgrade_upgrade_clean(self, alembic_db: str) -> None:
        cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{alembic_db}")
        command.downgrade(cfg, "-1")
        command.upgrade(cfg, "head")
        engine = create_engine(f"sqlite:///{alembic_db}")
        cols = {c["name"] for c in inspect(engine).get_columns("stocks")}
        assert "label_color" in cols


def _seed_stock(db: Session, ticker: str, label_color: str | None = None) -> Stock:
    stock = Stock(
        ticker=ticker,
        name=f"{ticker} Inc.",
        exchange="NASDAQ",
        is_active=True,
        added_at=datetime.now(timezone.utc),
        label_color=label_color,
    )
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


def _seed_bars(db: Session, stock_id: int, closes: list[float]) -> None:
    start = date(2025, 1, 1)
    for i, c in enumerate(closes):
        db.add(
            DailyBar(
                stock_id=stock_id,
                date=start + timedelta(days=i),
                open=c,
                high=c,
                low=c,
                close=c,
                volume=1000,
            )
        )
    db.commit()


def _recompute_all(db: Session) -> None:
    service = SignalService(db)
    for stock in db.query(Stock).all():
        service.recompute_for_stock(stock.id)


class TestGetSignalsLabelColorField:
    def test_s4_label_color_defaults_to_null(self, client, db_session: Session) -> None:
        stock = _seed_stock(db_session, "AAA")
        _seed_bars(db_session, stock.id, [100.0 + i * 0.05 for i in range(200)])
        _recompute_all(db_session)

        resp = client.get("/api/signals")
        assert resp.status_code == 200
        item = next(i for i in resp.json()["data"] if i["ticker"] == "AAA")
        assert "labelColor" in item
        assert item["labelColor"] is None

    def test_s5_label_color_passes_through(self, client, db_session: Session) -> None:
        stock = _seed_stock(db_session, "BBB", label_color="red")
        _seed_bars(db_session, stock.id, [100.0 + i * 0.05 for i in range(200)])
        _recompute_all(db_session)

        resp = client.get("/api/signals")
        assert resp.status_code == 200
        item = next(i for i in resp.json()["data"] if i["ticker"] == "BBB")
        assert item["labelColor"] == "red"
