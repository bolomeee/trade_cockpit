from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import SystemLog


def _seed_logs(db_session) -> list[SystemLog]:
    now = datetime.now(timezone.utc)
    rows = [
        SystemLog(level="OK", source="scheduler", message="refresh ok", created_at=now - timedelta(minutes=3)),
        SystemLog(level="INFO", source="watchlist", message="added AAPL", created_at=now - timedelta(minutes=2)),
        SystemLog(level="WARN", source="fmp", message="rate limited", created_at=now - timedelta(minutes=1)),
        SystemLog(level="ERROR", source="fmp", message="429 too many requests", detail="HTTP 429", created_at=now),
    ]
    for r in rows:
        db_session.add(r)
    db_session.commit()
    for r in rows:
        db_session.refresh(r)
    return rows


def test_list_empty(client):
    res = client.get("/api/logs")
    assert res.status_code == 200
    body = res.json()
    assert body["data"] == []
    assert body["message"] == "success"


def test_list_all_default_order(client, db_session):
    _seed_logs(db_session)
    res = client.get("/api/logs")
    assert res.status_code == 200
    items = res.json()["data"]
    assert [i["level"] for i in items] == ["ERROR", "WARN", "INFO", "OK"]


def test_camel_case_fields(client, db_session):
    _seed_logs(db_session)
    res = client.get("/api/logs")
    item = res.json()["data"][0]
    assert "createdAt" in item
    assert "created_at" not in item
    assert set(item.keys()) >= {"id", "level", "source", "message", "detail", "createdAt"}


@pytest.mark.parametrize("level", ["OK", "INFO", "WARN", "ERROR"])
def test_filter_by_level(client, db_session, level):
    _seed_logs(db_session)
    res = client.get(f"/api/logs?level={level}")
    assert res.status_code == 200
    items = res.json()["data"]
    assert len(items) == 1
    assert items[0]["level"] == level


def test_limit(client, db_session):
    _seed_logs(db_session)
    res = client.get("/api/logs?limit=2")
    assert res.status_code == 200
    items = res.json()["data"]
    assert len(items) == 2
    assert [i["level"] for i in items] == ["ERROR", "WARN"]


def test_invalid_level_returns_422(client):
    res = client.get("/api/logs?level=DEBUG")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_limit_out_of_range_returns_422(client):
    res = client.get("/api/logs?limit=0")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"

    res = client.get("/api/logs?limit=501")
    assert res.status_code == 422


def test_detail_field_exposed(client, db_session):
    _seed_logs(db_session)
    res = client.get("/api/logs?level=ERROR")
    item = res.json()["data"][0]
    assert item["detail"] == "HTTP 429"

    res = client.get("/api/logs?level=OK")
    assert res.json()["data"][0]["detail"] is None
