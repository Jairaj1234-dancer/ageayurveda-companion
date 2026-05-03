import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import ChatUser
from app.models.conversation import Conversation
from app.models.message import Message
from app.core.logging import logger


async def get_or_create_user(db: AsyncSession, session_id: str, language: str = "en") -> ChatUser:
    result = await db.execute(select(ChatUser).where(ChatUser.session_id == session_id))
    user = result.scalar_one_or_none()
    if not user:
        user = ChatUser(session_id=session_id, language=language)
        db.add(user)
        await db.flush()
        logger.info(f"Created new user for session {session_id}")
    return user


async def get_or_create_conversation(
    db: AsyncSession,
    user: ChatUser,
    conversation_id: str | None = None,
    language: str = "en",
    tenant_id=None,
) -> Conversation:
    if conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == uuid.UUID(conversation_id),
                Conversation.user_id == user.id,
            )
        )
        conv = result.scalar_one_or_none()
        if conv:
            return conv

    conv = Conversation(user_id=user.id, language=language, tenant_id=tenant_id)
    db.add(conv)
    await db.flush()
    return conv


async def add_message(
    db: AsyncSession,
    conversation: Conversation,
    role: str,
    content: str,
    citations: list[dict] | None = None,
    products: list[dict] | None = None,
    disclaimer: str | None = None,
    model_used: str | None = None,
    tokens_input: int | None = None,
    tokens_output: int | None = None,
    language: str = "en",
    retrievals: list[dict] | None = None,
    tenant_id=None,
) -> Message:
    msg = Message(
        conversation_id=conversation.id,
        tenant_id=tenant_id,
        role=role,
        content=content,
        citations=citations,
        products=products,
        disclaimer=disclaimer,
        model_used=model_used,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        language=language,
        retrievals=retrievals,
    )
    db.add(msg)
    conversation.message_count += 1
    if not conversation.title and role == "user":
        conversation.title = content[:100]
    await db.flush()
    return msg


async def get_recent_messages(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    limit: int = 6,
) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = list(result.scalars().all())
    messages.reverse()
    return messages


async def get_user_conversations(
    db: AsyncSession,
    session_id: str,
    limit: int = 20,
) -> list[Conversation]:
    result = await db.execute(
        select(Conversation)
        .join(ChatUser)
        .where(ChatUser.session_id == session_id)
        .options(selectinload(Conversation.messages))
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
