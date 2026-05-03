import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import GUID, JSONType


class QueryCache(Base):
    __tablename__ = "query_cache"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    query_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    query_text: Mapped[str] = mapped_column(Text)
    response_text: Mapped[str] = mapped_column(Text)
    citations: Mapped[dict | None] = mapped_column(JSONType())
    products: Mapped[dict | None] = mapped_column(JSONType())
    hit_count: Mapped[int] = mapped_column(Integer, default=1)
    language: Mapped[str] = mapped_column(String(5), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
