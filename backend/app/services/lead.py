from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.user import ChatUser
from app.core.logging import logger


async def capture_lead(
    db: AsyncSession,
    user: ChatUser,
    email: str,
    name: str | None = None,
    source: str = "chat_widget",
) -> Lead:
    """Capture a lead, updating user email if not set."""
    # Check if lead already exists for this user
    result = await db.execute(
        select(Lead).where(Lead.user_id == user.id, Lead.email == email)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    lead = Lead(user_id=user.id, email=email, name=name, source=source)
    db.add(lead)

    if not user.email:
        user.email = email

    await db.flush()
    logger.info(f"Lead captured: {email} from {source}")
    return lead


async def get_leads(
    db: AsyncSession,
    limit: int = 100,
    offset: int = 0,
) -> list[Lead]:
    result = await db.execute(
        select(Lead).order_by(Lead.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())
