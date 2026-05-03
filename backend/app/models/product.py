import uuid
from datetime import datetime

from sqlalchemy import String, Text, Float, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import GUID, JSONType


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    name_hi: Mapped[str | None] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    description_hi: Mapped[str | None] = mapped_column(Text)
    price: Mapped[float | None] = mapped_column(Float)
    image_url: Mapped[str | None] = mapped_column(String(512))
    shopify_url: Mapped[str | None] = mapped_column(String(512))
    category: Mapped[str | None] = mapped_column(String(100))
    ingredients: Mapped[dict | None] = mapped_column(JSONType())
    benefits: Mapped[dict | None] = mapped_column(JSONType())
    doshas: Mapped[dict | None] = mapped_column(JSONType())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
