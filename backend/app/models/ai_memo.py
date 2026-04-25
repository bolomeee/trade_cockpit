from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, Numeric, String, Text

from app.models import Base


class AiMemo(Base):
    __tablename__ = "ai_memos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_type = Column(String(32), nullable=False, index=True)
    input_hash = Column(String(64), nullable=False, index=True)
    input_json = Column(Text, nullable=False)
    output_json = Column(Text, nullable=False)
    schema_version = Column(String(16), nullable=False)
    model_used = Column(String(64), nullable=False)
    tier = Column(String(16), nullable=False)
    tokens_in = Column(Integer, nullable=False)
    tokens_out = Column(Integer, nullable=False)
    cost_usd = Column(Numeric(10, 6), nullable=False)
    latency_ms = Column(Integer, nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
