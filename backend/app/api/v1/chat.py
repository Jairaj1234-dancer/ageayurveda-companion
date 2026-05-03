import json

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import Tenant
from app.schemas.chat import ChatRequest, ChatResponse, ConversationHistory, MessageOut, Citation, ProductRecommendation
from app.services.conversation import (
    get_or_create_user,
    get_or_create_conversation,
    add_message,
    get_recent_messages,
    get_user_conversations,
)
from app.services.claude import generate_response, generate_stream
from app.services.grounded_chat import generate_grounded_response, generate_grounded_stream
from app.services.citation import extract_citations
from app.services.disclaimer import get_disclaimer
from app.services.language import detect_language
from app.core.limiter import limiter
from app.core import rate_limit as rl
from app.core.security import sanitize_input
from app.core.logging import logger

_settings = get_settings()


async def _resolve_tenant(request: Request, db: AsyncSession) -> Tenant | None:
    """If the request carries `Authorization: Bearer ageak_...`, look up the
    tenant. Returns None when no auth header — falls through to the platform's
    global Anthropic key (existing single-tenant behaviour).

    Raises 401 when an auth header is present but the key is unknown / inactive,
    and 403 when the tenant has no Anthropic key configured.
    """
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[len("Bearer "):].strip()
    if not token.startswith("ageak_"):
        return None  # Not a tenant key — let other auth schemes pass through.

    result = await db.execute(select(Tenant).where(Tenant.api_key == token))
    tenant = result.scalar_one_or_none()
    if tenant is None or not tenant.active:
        raise HTTPException(status_code=401, detail="Invalid or revoked tenant key")
    if not tenant.anthropic_api_key:
        raise HTTPException(
            status_code=403,
            detail=f"Tenant '{tenant.name}' has no Anthropic API key configured",
        )
    return tenant

router = APIRouter(prefix="/chat")


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Main chat endpoint - non-streaming."""
    message = sanitize_input(request.message)
    language = request.language
    if language == "auto":
        language = detect_language(message)

    user = await get_or_create_user(db, request.session_id, language)
    conversation = await get_or_create_conversation(db, user, request.conversation_id, language)

    # Save user message
    await add_message(db, conversation, "user", message, language=language)

    # Generate response (static rule-based engine)
    result = await generate_response(message, language=language)

    # Post-processing
    citations = extract_citations(result["content"])
    products = result.get("products") or []
    disclaimer = get_disclaimer(message, language)

    # Save assistant message
    await add_message(
        db, conversation, "assistant", result["content"],
        citations=[c for c in citations] if citations else None,
        products=products if products else None,
        disclaimer=disclaimer,
        model_used=result.get("model"),
        tokens_input=result.get("tokens_input"),
        tokens_output=result.get("tokens_output"),
        language=language,
    )

    await db.commit()

    return ChatResponse(
        message=result["content"],
        conversation_id=str(conversation.id),
        citations=[Citation(**c) for c in citations],
        products=[ProductRecommendation(**p) for p in products],
        disclaimer=disclaimer,
        language=language,
    )


@router.post("/stream")
async def chat_stream(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Streaming chat endpoint via SSE."""
    message = sanitize_input(request.message)
    language = request.language
    if language == "auto":
        language = detect_language(message)

    user = await get_or_create_user(db, request.session_id, language)
    conversation = await get_or_create_conversation(db, user, request.conversation_id, language)

    await add_message(db, conversation, "user", message, language=language)

    async def event_generator():
        async for event in generate_stream(message, language=language):
            if event["type"] == "token":
                yield f"data: {json.dumps({'type': 'token', 'content': event['content']})}\n\n"
            elif event["type"] == "done":
                citations = extract_citations(event.get("content", ""))
                products = event.get("products") or []
                disclaimer = get_disclaimer(message, language)

                await add_message(
                    db, conversation, "assistant", event["content"],
                    citations=citations if citations else None,
                    products=products if products else None,
                    disclaimer=disclaimer,
                    model_used=event.get("model"),
                    tokens_input=event.get("tokens_input"),
                    tokens_output=event.get("tokens_output"),
                    language=language,
                )
                await db.commit()

                yield f"data: {json.dumps({'type': 'done', 'conversation_id': str(conversation.id), 'citations': citations, 'products': products, 'disclaimer': disclaimer})}\n\n"
            elif event["type"] == "error":
                yield f"data: {json.dumps({'type': 'error', 'content': event['content']})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _history_for_grounding(messages) -> list[dict]:
    """Convert ORM messages into the {role, content} list the grounded chat
    expects. Excludes the most recent user message — that's the current turn.
    """
    out: list[dict] = []
    for m in messages[:-1] if messages else []:
        out.append({"role": m.role, "content": m.content})
    return out


def _product_for_response(p: dict) -> dict:
    """Map the tool's product shape to the ProductRecommendation schema."""
    return {
        "id": p["id"],
        "name": p["name"],
        "slug": p["slug"],
        "price": p.get("price"),
        "image_url": p.get("image_url"),
        "shopify_url": p.get("shopify_url"),
        "dosha_balance": p.get("why"),
        "score": 1.0,
    }


def _parse_global_limit() -> int:
    """Parse settings.rate_limit_grounded ("N/minute") into an int."""
    raw = _settings.rate_limit_grounded.split("/")[0].strip()
    try:
        return int(raw)
    except ValueError:
        return 10


def _check_grounded_rate_limit(request: Request, tenant: Tenant | None) -> None:
    """Dynamic per-tenant rate limit. When a tenant is present, use their
    stored limit; otherwise fall back to the global IP-based default."""
    if tenant is not None:
        rl.check(f"tenant:{tenant.id}", tenant.rate_limit_per_minute)
    else:
        ip = request.client.host if request.client else "unknown"
        rl.check(f"ip:{ip}", _parse_global_limit())


def _resolve_sources(tenant: Tenant | None, body_sources: list[str] | None) -> list[str] | None:
    """Compute the effective source allowlist for retrieval.

    - No tenant + no body filter → None (full corpus)
    - Tenant only → tenant's allowed_sources
    - Body only → body sources
    - Both → intersection (tenant restriction always applies; body can narrow further)
    """
    if not tenant or not tenant.allowed_sources:
        return body_sources
    if not body_sources:
        return tenant.allowed_sources
    return [s for s in body_sources if s in tenant.allowed_sources]


@router.post("/grounded", response_model=ChatResponse)
async def chat_grounded(
    request: Request,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Classical-text-grounded chat — non-streaming.

    Pipeline: retrieve top-K corpus chunks → Claude with grounding context →
    parse citations from response → save with retrievals + disclaimer.

    Rate limited dynamically — per-tenant when authenticated, per-IP at the
    global default otherwise. Tenant Bearer token (`ageak_…`) selects the
    tenant's BYO Anthropic key + source allowlist + rate limit.
    """
    tenant = await _resolve_tenant(request, db)
    _check_grounded_rate_limit(request, tenant)
    message = sanitize_input(body.message)
    language = body.language
    if language == "auto":
        language = detect_language(message)

    user = await get_or_create_user(db, body.session_id, language)
    conversation = await get_or_create_conversation(
        db, user, body.conversation_id, language, tenant_id=tenant.id if tenant else None,
    )

    await add_message(db, conversation, "user", message, language=language, tenant_id=tenant.id if tenant else None)
    history_msgs = await get_recent_messages(db, conversation.id, limit=8)
    history = _history_for_grounding(history_msgs)

    effective_sources = _resolve_sources(tenant, body.sources)
    try:
        result = await generate_grounded_response(
            db, message,
            history=history,
            language=language,
            sources=effective_sources,
            anthropic_api_key=tenant.anthropic_api_key if tenant else None,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except anthropic.AuthenticationError:
        raise HTTPException(
            status_code=502,
            detail="Upstream LLM authentication failed — check the Anthropic API key.",
        )
    except anthropic.RateLimitError:
        raise HTTPException(
            status_code=502,
            detail="Upstream LLM rate-limited — try again in a moment.",
        )
    except anthropic.APIError as e:
        logger.exception("anthropic API error in /grounded")
        raise HTTPException(
            status_code=502,
            detail=f"Upstream LLM error: {e.__class__.__name__}",
        )

    citations = extract_citations(result["content"])
    disclaimer = get_disclaimer(message, language)
    retrievals = result.get("retrievals") or []
    products = result.get("products") or []

    await add_message(
        db, conversation, "assistant", result["content"],
        citations=citations if citations else None,
        products=products if products else None,
        disclaimer=disclaimer,
        model_used=result.get("model"),
        tokens_input=result.get("tokens_input"),
        tokens_output=result.get("tokens_output"),
        language=language,
        retrievals=retrievals if retrievals else None,
        tenant_id=tenant.id if tenant else None,
    )
    await db.commit()

    return ChatResponse(
        message=result["content"],
        conversation_id=str(conversation.id),
        citations=[Citation(**c) for c in citations],
        products=[ProductRecommendation(**_product_for_response(p)) for p in products],
        disclaimer=disclaimer,
        language=language,
    )


@router.post("/grounded/stream")
async def chat_grounded_stream(
    request: Request,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Classical-text-grounded chat — SSE streaming.

    Tenant-aware (Bearer ageak_…). Same per-tenant rate limit + source
    allowlist as the non-streaming endpoint.
    """
    tenant = await _resolve_tenant(request, db)
    _check_grounded_rate_limit(request, tenant)
    message = sanitize_input(body.message)
    language = body.language
    if language == "auto":
        language = detect_language(message)

    user = await get_or_create_user(db, body.session_id, language)
    conversation = await get_or_create_conversation(
        db, user, body.conversation_id, language, tenant_id=tenant.id if tenant else None,
    )

    await add_message(db, conversation, "user", message, language=language, tenant_id=tenant.id if tenant else None)
    history_msgs = await get_recent_messages(db, conversation.id, limit=8)
    history = _history_for_grounding(history_msgs)

    effective_sources = _resolve_sources(tenant, body.sources)
    tenant_anthropic_key = tenant.anthropic_api_key if tenant else None

    async def event_generator():
        async for event in generate_grounded_stream(
            db, message,
            history=history,
            language=language,
            sources=effective_sources,
            anthropic_api_key=tenant_anthropic_key,
        ):
            if event["type"] == "token":
                yield f"data: {json.dumps({'type': 'token', 'content': event['content']})}\n\n"
            elif event["type"] == "tool_use":
                # Emit products as soon as the tool returns so the widget can
                # render product cards before the final text begins streaming.
                yield f"data: {json.dumps({'type': 'tool_use', 'name': event.get('name'), 'products': event.get('products') or []})}\n\n"
            elif event["type"] == "done":
                citations = extract_citations(event.get("content", ""))
                disclaimer = get_disclaimer(message, language)
                retrievals = event.get("retrievals") or []
                products = event.get("products") or []

                await add_message(
                    db, conversation, "assistant", event["content"],
                    citations=citations if citations else None,
                    products=products if products else None,
                    disclaimer=disclaimer,
                    model_used=event.get("model"),
                    tokens_input=event.get("tokens_input"),
                    tokens_output=event.get("tokens_output"),
                    language=language,
                    retrievals=retrievals if retrievals else None,
                    tenant_id=tenant.id if tenant else None,
                )
                await db.commit()

                yield f"data: {json.dumps({'type': 'done', 'conversation_id': str(conversation.id), 'citations': citations, 'disclaimer': disclaimer, 'retrievals': retrievals, 'products': products})}\n\n"
            elif event["type"] == "error":
                yield f"data: {json.dumps({'type': 'error', 'content': event['content']})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history", response_model=list[ConversationHistory])
async def get_history(
    session_id: str = Query(..., min_length=1, max_length=64),
    db: AsyncSession = Depends(get_db),
):
    conversations = await get_user_conversations(db, session_id)
    return [
        ConversationHistory(
            conversation_id=str(c.id),
            title=c.title,
            messages=[
                MessageOut(
                    role=m.role,
                    content=m.content,
                    citations=[Citation(**ci) for ci in (m.citations or [])],
                    products=[ProductRecommendation(**p) for p in (m.products or [])],
                    disclaimer=m.disclaimer,
                    created_at=m.created_at,
                )
                for m in c.messages
            ],
            created_at=c.created_at,
        )
        for c in conversations
    ]
