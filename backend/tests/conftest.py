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
from app.dependencies import get_polygon_client, get_session_factory
from app.main import app
from app.models import Base


class FakePolygon:
    """Programmable stand-in for PolygonClient used in tests."""

    def __init__(self) -> None:
        self.search_results: list[Any] = []
        self.search_calls: list[tuple[str, int]] = []
        self.search_exc: Exception | None = None

    def search_tickers(self, query: str, limit: int = 10) -> list[Any]:
        self.search_calls.append((query, limit))
        if self.search_exc is not None:
            raise self.search_exc
        return list(self.search_results)


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
def mock_polygon() -> FakePolygon:
    return FakePolygon()


@pytest.fixture
def client(session_engine, mock_polygon) -> Generator[TestClient, None, None]:
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
    app.dependency_overrides[get_polygon_client] = lambda: mock_polygon
    app.dependency_overrides[get_session_factory] = lambda: TestingSession

    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_polygon_client, None)
        app.dependency_overrides.pop(get_session_factory, None)
