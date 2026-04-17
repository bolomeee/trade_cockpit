from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import SystemLog
from app.repositories.system_log_repository import SystemLogRepository


class TestSystemLogRepository:
    def test_create_persists_with_timestamp(self, db_session):
        repo = SystemLogRepository(db_session)
        log = repo.create("OK", "data_refresh", "AAPL refreshed (5 bars)")
        assert log.id is not None
        assert log.level == "OK"
        assert log.source == "data_refresh"
        assert log.message == "AAPL refreshed (5 bars)"
        assert log.detail is None
        assert log.created_at is not None

    def test_create_truncates_message_to_500(self, db_session):
        repo = SystemLogRepository(db_session)
        long = "x" * 700
        log = repo.create("INFO", "test", long)
        assert len(log.message) == 500

    def test_create_rejects_invalid_level(self, db_session):
        repo = SystemLogRepository(db_session)
        with pytest.raises(ValueError):
            repo.create("CRITICAL", "test", "nope")

    def test_purge_older_than_drops_old_rows(self, db_session):
        repo = SystemLogRepository(db_session)
        now = datetime.now(timezone.utc)
        # Directly insert rows with controlled created_at
        old = SystemLog(
            level="INFO",
            source="t",
            message="old",
            created_at=now - timedelta(days=10),
        )
        fresh = SystemLog(
            level="INFO",
            source="t",
            message="fresh",
            created_at=now - timedelta(days=1),
        )
        db_session.add_all([old, fresh])
        db_session.commit()

        deleted = repo.purge_older_than(days=7)
        assert deleted == 1

        remaining = repo.list_recent()
        assert len(remaining) == 1
        assert remaining[0].message == "fresh"

    def test_list_recent_orders_desc_and_filters_level(self, db_session):
        repo = SystemLogRepository(db_session)
        repo.create("OK", "s", "a")
        repo.create("ERROR", "s", "b")
        repo.create("OK", "s", "c")

        all_logs = repo.list_recent()
        assert [log.message for log in all_logs] == ["c", "b", "a"]

        errors = repo.list_recent(level="ERROR")
        assert len(errors) == 1
        assert errors[0].message == "b"

    def test_list_recent_respects_limit(self, db_session):
        repo = SystemLogRepository(db_session)
        for i in range(5):
            repo.create("INFO", "s", f"msg-{i}")
        assert len(repo.list_recent(limit=3)) == 3
