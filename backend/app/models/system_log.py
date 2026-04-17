from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.models import Base


class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(String(10), nullable=False)
    source = Column(String(50), nullable=False)
    message = Column(String(500), nullable=False)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
