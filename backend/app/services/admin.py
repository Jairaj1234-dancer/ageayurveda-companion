from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_user import AdminUser
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.lead import Lead
from app.models.prakriti_result import PrakritiResult
from app.core.security import verify_password, hash_password
from app.core.logging import logger


async def authenticate_admin(db: AsyncSession, username: str, password: str) -> AdminUser | None:
    result = await db.execute(
        select(AdminUser).where(AdminUser.username == username, AdminUser.is_active == True)
    )
    admin = result.scalar_one_or_none()
    if admin and verify_password(password, admin.password_hash):
        admin.last_login = datetime.now(timezone.utc)
        await db.flush()
        return admin
    return None


async def create_admin_user(db: AsyncSession, username: str, password: str) -> AdminUser:
    admin = AdminUser(username=username, password_hash=hash_password(password))
    db.add(admin)
    await db.flush()
    return admin


async def get_dashboard_stats(db: AsyncSession) -> dict:
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    total_conversations = (await db.execute(select(func.count(Conversation.id)))).scalar() or 0
    total_messages = (await db.execute(select(func.count(Message.id)))).scalar() or 0
    total_leads = (await db.execute(select(func.count(Lead.id)))).scalar() or 0
    total_prakriti = (await db.execute(select(func.count(PrakritiResult.id)))).scalar() or 0

    conversations_today = (
        await db.execute(
            select(func.count(Conversation.id)).where(Conversation.created_at >= today_start)
        )
    ).scalar() or 0

    # Estimate API cost from token usage today
    cost_result = await db.execute(
        select(
            func.coalesce(func.sum(Message.tokens_input), 0),
            func.coalesce(func.sum(Message.tokens_output), 0),
        ).where(Message.created_at >= today_start, Message.role == "assistant")
    )
    row = cost_result.one()
    # Rough cost: input $3/MTok, output $15/MTok (Sonnet average)
    api_cost = (row[0] * 3 / 1_000_000) + (row[1] * 15 / 1_000_000)

    return {
        "total_conversations": total_conversations,
        "total_messages": total_messages,
        "total_leads": total_leads,
        "total_prakriti_assessments": total_prakriti,
        "conversations_today": conversations_today,
        "api_cost_today": round(api_cost, 4),
    }


async def get_conversations_paginated(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 20,
    search: str = "",
) -> tuple[list, int]:
    from app.models.user import ChatUser
    from sqlalchemy.orm import selectinload

    query = select(Conversation).options(selectinload(Conversation.user))
    count_query = select(func.count(Conversation.id))

    if search:
        query = query.where(Conversation.title.ilike(f"%{search}%"))
        count_query = count_query.where(Conversation.title.ilike(f"%{search}%"))

    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Conversation.updated_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    conversations = result.scalars().all()
    return conversations, total


async def get_conversation_detail(db: AsyncSession, conversation_id: str) -> dict | None:
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id)
    )
    convo = result.scalar_one_or_none()
    if not convo:
        return None

    return {
        "id": str(convo.id),
        "title": convo.title,
        "language": convo.language,
        "message_count": convo.message_count,
        "created_at": convo.created_at.isoformat() if convo.created_at else "",
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "citations": str(m.citations) if m.citations else None,
                "products": str(m.products) if m.products else None,
                "disclaimer": m.disclaimer,
                "model_used": m.model_used,
                "tokens_input": m.tokens_input,
                "tokens_output": m.tokens_output,
                "language": m.language,
                "created_at": m.created_at.isoformat() if m.created_at else "",
            }
            for m in convo.messages
        ],
    }
