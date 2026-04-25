"""AiMemoRepository: persist + dedup lookup for ai_memos (D069)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.ai_memo import AiMemo


def compute_input_hash(input_dict: dict[str, Any]) -> str:
    """SHA-256 of canonical JSON (sort_keys + compact separators) → 64 hex chars.

    Module-level helper so callers can compute the hash without instantiating
    a DB-bound object — the gateway uses it once for both find_cached and write.
    """
    canonical = json.dumps(input_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class AiMemoRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_cached(
        self,
        *,
        task_type: str,
        input_hash: str,
        schema_version: str,
        ttl_hours: int,
        now: datetime | None = None,
    ) -> AiMemo | None:
        """Return latest matching memo within TTL window, else None.

        Hit conditions (all required):
          - task_type 相同
          - input_hash 相同
          - schema_version 相同（D069: schema 升级旧 memo 自动 invalidate）
          - created_at > now - ttl_hours
        """
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=ttl_hours)
        return (
            self.db.query(AiMemo)
            .filter(
                AiMemo.task_type == task_type,
                AiMemo.input_hash == input_hash,
                AiMemo.schema_version == schema_version,
                AiMemo.created_at > cutoff,
            )
            .order_by(AiMemo.created_at.desc())
            .first()
        )

    def write(
        self,
        *,
        task_type: str,
        input_dict: dict[str, Any],
        output_dict: dict[str, Any],
        schema_version: str,
        model_used: str,
        tier: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: Decimal,
        latency_ms: int,
        input_hash: str | None = None,
    ) -> int:
        """Insert one ai_memos row. Returns AiMemo.id.

        Caller may pass precomputed input_hash to avoid double-hashing
        (gateway computes hash once, uses it for find_cached then write).
        """
        if input_hash is None:
            input_hash = compute_input_hash(input_dict)
        memo = AiMemo(
            task_type=task_type,
            input_hash=input_hash,
            input_json=_canonical_json(input_dict),
            output_json=_canonical_json(output_dict),
            schema_version=schema_version,
            model_used=model_used,
            tier=tier,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )
        self.db.add(memo)
        self.db.commit()
        self.db.refresh(memo)
        return memo.id
