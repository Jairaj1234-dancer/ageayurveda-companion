"""Tenant model — represents a B2B customer using the grounded-chat platform.

Each tenant gets:
  - A public api_key (`ageak_<random>`) — sent in the Authorization header
  - Their own anthropic_api_key (BYO model billing — they pay Anthropic, we
    don't carry inference cost). Stored in plaintext for now; can move to
    a KMS-backed encrypted column when the customer count justifies it.
  - An optional source allowlist — `["Charaka Samhita"]` restricts retrieval
    to that subset of the corpus
  - A per-tenant rate limit (overrides the global default)
  - An active flag for soft-revocation

The grounded chat endpoints look for `Authorization: Bearer <api_key>`. If
present and valid, the tenant's BYO Anthropic key + source allowlist apply.
If absent, falls back to the platform's global key (i.e. the existing
single-tenant behaviour) — which means existing widget deployments keep
working without changes.
"""
import secrets
import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import GUID, JSONType


def generate_api_key() -> str:
    """Public tenant key. Prefix lets us spot leaks in logs and rotate."""
    return f"ageak_{secrets.token_urlsafe(32)}"


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    api_key: Mapped[str] = mapped_column(String(80), unique=True, index=True, default=generate_api_key)
    anthropic_api_key: Mapped[str | None] = mapped_column(String(200))
    allowed_sources: Mapped[list | None] = mapped_column(JSONType())
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=10)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    notes: Mapped[str | None] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
