import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.types import GUID, JSONType


class PrakritiResult(Base):
    __tablename__ = "prakriti_results"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("chat_users.id"), index=True)
    constitution: Mapped[str] = mapped_column(String(50))
    scores: Mapped[dict] = mapped_column(JSONType())
    answers: Mapped[dict] = mapped_column(JSONType())
    recommendations: Mapped[dict | None] = mapped_column(JSONType())
    language: Mapped[str] = mapped_column(String(5), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["ChatUser"] = relationship(back_populates="prakriti_results")
