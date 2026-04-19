from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any

import pytest

os.environ.setdefault("MA150_DISABLE_SCHEDULER", "1")
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.dependencies import get_fmp_client, get_session_factory
from app.main import app
from app.models import Base


class FakeFMP:
    """Programmable stand-in for FmpClient used in tests.

    Method signatures mirror app.external.fmp_client.FmpClient so service-layer
    code can swap the dependency without changes elsewhere.
    """

    def __init__(self) -> None:
        self.search_results: list[Any] = []
        self.search_calls: list[tuple[str, int]] = []
        self.search_exc: Exception | None = None

        self.daily_bars_results: list[Any] = []
        self.daily_bars_calls: list[tuple[str, Any, Any]] = []

        self.index_bars_results: dict[str, list[Any]] = {}
        self.index_bars_calls: list[tuple[str, int]] = []
        self.index_bars_exc: dict[str, Exception] = {}

        self.treasury_result: dict[str, Any] = {}
        self.treasury_calls: int = 0
        self.treasury_exc: Exception | None = None

        self.ratios_results: dict[str, dict[str, Any] | None] = {}
        self.ratios_calls: list[str] = []

        self.key_metrics_results: dict[str, dict[str, Any] | None] = {}
        self.key_metrics_calls: list[str] = []

    def search_tickers(self, query: str, limit: int = 10) -> list[Any]:
        self.search_calls.append((query, limit))
        if self.search_exc is not None:
            raise self.search_exc
        return list(self.search_results)

    def get_daily_bars(self, symbol: str, from_date, to_date) -> list[Any]:
        self.daily_bars_calls.append((symbol, from_date, to_date))
        return list(self.daily_bars_results)

    def get_index_recent_bars(self, symbol: str, days: int = 10) -> list[Any]:
        self.index_bars_calls.append((symbol, days))
        if symbol in self.index_bars_exc:
            raise self.index_bars_exc[symbol]
        return list(self.index_bars_results.get(symbol, []))

    def get_treasury_10y_latest(self) -> dict[str, Any]:
        self.treasury_calls += 1
        if self.treasury_exc is not None:
            raise self.treasury_exc
        return dict(self.treasury_result)

    def get_ratios_ttm(self, symbol: str) -> dict[str, Any] | None:
        self.ratios_calls.append(symbol)
        return self.ratios_results.get(symbol)

    def get_key_metrics_ttm(self, symbol: str) -> dict[str, Any] | None:
        self.key_metrics_calls.append(symbol)
        return self.key_metrics_results.get(symbol)


@pytest.fixture
def session_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def db_session(session_engine) -> Generator[Session, None, None]:
    TestingSession = sessionmaker(
        bind=session_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def fake_fmp() -> FakeFMP:
    return FakeFMP()


@pytest.fixture
def client(session_engine, fake_fmp) -> Generator[TestClient, None, None]:
    TestingSession = sessionmaker(
        bind=session_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_fmp_client] = lambda: fake_fmp
    app.dependency_overrides[get_session_factory] = lambda: TestingSession

    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_fmp_client, None)
        app.dependency_overrides.pop(get_session_factory, None)
