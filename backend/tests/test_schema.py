"""Verify Alembic migration produces the schema defined in DATA-MODEL.md."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


EXPECTED_TABLES = {
    "stocks",
    "daily_bars",
    "signals",
    "pullbacks",
    "market_indices",
    "system_logs",
    "journal_entries",
    "market_scan_universe",
    "market_breakout_scans",
    "daily_payload_cache",
    "news_articles_cache",
    "earnings_events",  # F204-a
    "market_regime_snapshots",  # F201-a
}

EXPECTED_COLUMNS: dict[str, set[str]] = {
    "stocks": {
        "id", "ticker", "name", "exchange", "is_active", "added_at", "last_refreshed_at",
        "shares_float", "shares_float_refreshed_at",
    },
    "daily_bars": {"id", "stock_id", "date", "open", "high", "low", "close", "volume"},
    "signals": {
        "id", "stock_id", "date", "signal_type", "ma150_value",
        "close_price", "distance_pct", "slope_positive", "slope_value",
    },
    "pullbacks": {
        "id", "stock_id", "date", "close_price", "ma150_value",
        "distance_pct", "return_10d", "return_20d", "return_30d",
    },
    "market_indices": {"id", "symbol", "name", "date", "close", "prev_close", "change_pct"},
    "system_logs": {"id", "level", "source", "message", "detail", "created_at"},
    "journal_entries": {
        "id", "stock_id", "action", "price", "date", "position_size",
        "stop_loss", "target_price", "reason", "reference", "created_at", "updated_at",
    },
    "market_scan_universe": {
        "id", "ticker", "company_name", "exchange", "market_cap",
        "last_seen_at", "added_at",
    },
    "market_breakout_scans": {
        "id", "scan_date", "ticker", "company_name", "signal_type",
        "close_price", "ma150_value", "pct_above_ma150", "slope_value",
        "volume", "volume_ratio_20", "market_cap", "scanned_at",
    },
}


@pytest.fixture
def migrated_engine():
    backend_root = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        url = f"sqlite:///{db_path}"

        cfg = Config(str(backend_root / "alembic.ini"))
        cfg.set_main_option("script_location", str(backend_root / "alembic"))
        cfg.set_main_option("sqlalchemy.url", url)

        command.upgrade(cfg, "head")
        engine = create_engine(url)
        try:
            yield engine
        finally:
            engine.dispose()


def test_all_tables_created(migrated_engine) -> None:
    inspector = inspect(migrated_engine)
    tables = set(inspector.get_table_names()) - {"alembic_version"}
    assert tables == EXPECTED_TABLES


@pytest.mark.parametrize("table,expected", sorted(EXPECTED_COLUMNS.items()))
def test_columns_match_data_model(migrated_engine, table: str, expected: set[str]) -> None:
    inspector = inspect(migrated_engine)
    actual = {col["name"] for col in inspector.get_columns(table)}
    assert actual == expected, f"{table}: expected {expected}, got {actual}"


def test_unique_constraints(migrated_engine) -> None:
    inspector = inspect(migrated_engine)
    # stocks.ticker unique
    stock_uniques = inspector.get_unique_constraints("stocks")
    assert any("ticker" in uc["column_names"] for uc in stock_uniques) or any(
        idx["unique"] and idx["column_names"] == ["ticker"]
        for idx in inspector.get_indexes("stocks")
    )
    # daily_bars composite unique
    db_uniques = inspector.get_unique_constraints("daily_bars")
    assert any(set(uc["column_names"]) == {"stock_id", "date"} for uc in db_uniques)


def test_migration_003_signal_type_upgrade_downgrade_roundtrip() -> None:
    """F106-a alembic 003: upgrade adds signal_type/volume/volume_ratio_20 +
    swaps unique constraint; downgrade restores pre-F106 schema.
    """
    backend_root = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        url = f"sqlite:///{db_path}"
        cfg = Config(str(backend_root / "alembic.ini"))
        cfg.set_main_option("script_location", str(backend_root / "alembic"))
        cfg.set_main_option("sqlalchemy.url", url)

        # First bring to pre-F106 head (002), confirm baseline schema.
        command.upgrade(cfg, "002_f105_market_scan_tables")
        engine = create_engine(url)
        try:
            inspector = inspect(engine)
            cols = {c["name"] for c in inspector.get_columns("market_breakout_scans")}
            assert "signal_type" not in cols
            assert "volume" not in cols
            uniques = inspector.get_unique_constraints("market_breakout_scans")
            assert any(
                set(u["column_names"]) == {"scan_date", "ticker"}
                and u["name"] == "uq_breakout_scan_date_ticker"
                for u in uniques
            )
        finally:
            engine.dispose()

        # Upgrade to 003 head.
        command.upgrade(cfg, "head")
        engine = create_engine(url)
        try:
            inspector = inspect(engine)
            cols = {c["name"] for c in inspector.get_columns("market_breakout_scans")}
            assert {"signal_type", "volume", "volume_ratio_20"} <= cols
            uniques = inspector.get_unique_constraints("market_breakout_scans")
            assert any(
                set(u["column_names"]) == {"scan_date", "ticker", "signal_type"}
                and u["name"] == "uq_breakout_scan_date_ticker_signal"
                for u in uniques
            )
            # Old constraint name must be gone.
            assert not any(
                u["name"] == "uq_breakout_scan_date_ticker" for u in uniques
            )
            # signal_type has an index for filter queries.
            indexes = inspector.get_indexes("market_breakout_scans")
            assert any(ix["column_names"] == ["signal_type"] for ix in indexes)
        finally:
            engine.dispose()

        # Downgrade one step back to 002 and verify schema is pre-F106 again.
        command.downgrade(cfg, "002_f105_market_scan_tables")
        engine = create_engine(url)
        try:
            inspector = inspect(engine)
            cols = {c["name"] for c in inspector.get_columns("market_breakout_scans")}
            assert "signal_type" not in cols
            assert "volume" not in cols
            assert "volume_ratio_20" not in cols
            uniques = inspector.get_unique_constraints("market_breakout_scans")
            assert any(
                set(u["column_names"]) == {"scan_date", "ticker"}
                and u["name"] == "uq_breakout_scan_date_ticker"
                for u in uniques
            )
        finally:
            engine.dispose()


def test_downgrade_removes_all_tables() -> None:
    backend_root = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        url = f"sqlite:///{db_path}"
        cfg = Config(str(backend_root / "alembic.ini"))
        cfg.set_main_option("script_location", str(backend_root / "alembic"))
        cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")
        engine = create_engine(url)
        try:
            inspector = inspect(engine)
            remaining = set(inspector.get_table_names()) - {"alembic_version"}
            assert remaining == set()
        finally:
            engine.dispose()
