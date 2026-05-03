import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    Message, CorpusChunk, Tenant, Dravya, Formulation, FormulationIngredient, Vyadhi,
    ModernEvidence, Procedure, ParikshaParam, DiagnosticPattern, KnowledgeEdge,
)
from app.services.pariksha_scoring import score_findings
from app.services import kg as kg_service
from app.models.tenant import generate_api_key
from app.schemas.admin import AdminLogin, AdminToken, DashboardStats
from app.core.security import create_access_token, verify_token
from app.services.admin import (
    authenticate_admin,
    get_dashboard_stats,
    get_conversations_paginated,
    get_conversation_detail,
)
from app.services.lead import get_leads
from app.schemas.lead import LeadOut

router = APIRouter(prefix="/admin")


@router.post("/login", response_model=AdminToken)
async def admin_login(request: AdminLogin, db: AsyncSession = Depends(get_db)):
    admin = await authenticate_admin(db, request.username, request.password)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token({"sub": str(admin.id), "username": admin.username})
    return AdminToken(access_token=token)


@router.get("/dashboard", response_model=DashboardStats)
async def dashboard(
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    stats = await get_dashboard_stats(db)
    return DashboardStats(**stats)


@router.get("/conversations")
async def admin_conversations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    conversations, total = await get_conversations_paginated(db, page, per_page, search)
    return {
        "conversations": [
            {
                "id": str(c.id),
                "title": c.title,
                "language": c.language,
                "message_count": c.message_count,
                "created_at": c.created_at.isoformat() if c.created_at else "",
                "updated_at": c.updated_at.isoformat() if c.updated_at else "",
                "user_email": c.user.email if c.user else None,
            }
            for c in conversations
        ],
        "total": total,
    }


@router.get("/conversations/{conversation_id}")
async def admin_conversation_detail(
    conversation_id: str,
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    detail = await get_conversation_detail(db, conversation_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return detail


@router.get("/grounded/messages/{message_id}/retrievals")
async def admin_message_retrievals(
    message_id: str,
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    """Inspect which corpus chunks grounded a specific assistant message."""
    try:
        mid = uuid.UUID(message_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid message_id")

    msg = (await db.execute(select(Message).where(Message.id == mid))).scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    retrievals = msg.retrievals or []
    chunk_ids = [r.get("chunk_id") for r in retrievals if r.get("chunk_id")]

    chunks_by_id: dict[str, CorpusChunk] = {}
    if chunk_ids:
        try:
            uuids = [uuid.UUID(cid) for cid in chunk_ids]
        except ValueError:
            uuids = []
        if uuids:
            result = await db.execute(select(CorpusChunk).where(CorpusChunk.id.in_(uuids)))
            chunks_by_id = {str(c.id): c for c in result.scalars().all()}

    enriched = []
    for r in retrievals:
        chunk = chunks_by_id.get(r.get("chunk_id"))
        enriched.append({
            "label": r.get("label"),
            "score": r.get("score"),
            "chunk_id": r.get("chunk_id"),
            "source": chunk.source if chunk else None,
            "section": chunk.section if chunk else None,
            "chapter": chunk.chapter if chunk else None,
            "verse": (
                f"{chunk.verse_start}-{chunk.verse_end}" if chunk and chunk.verse_end and chunk.verse_end != chunk.verse_start
                else (chunk.verse_start if chunk else None)
            ),
            "english": chunk.english if chunk else None,
            "sanskrit": chunk.sanskrit if chunk else None,
        })

    return {
        "message_id": str(msg.id),
        "model_used": msg.model_used,
        "tokens_input": msg.tokens_input,
        "tokens_output": msg.tokens_output,
        "content": msg.content,
        "citations": msg.citations or [],
        "retrievals": enriched,
    }


@router.get("/grounded/corpus")
async def admin_corpus_overview(
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    """Summary of what's in the corpus_chunks table."""
    total = (await db.execute(select(func.count(CorpusChunk.id)))).scalar_one()
    by_source = await db.execute(
        select(CorpusChunk.source, func.count(CorpusChunk.id))
        .group_by(CorpusChunk.source)
    )
    return {
        "total_chunks": total,
        "by_source": [{"source": s, "count": c} for s, c in by_source.all()],
    }


def _tenant_to_dict(t: Tenant, include_secret: bool = False) -> dict:
    out = {
        "id": str(t.id),
        "name": t.name,
        "active": t.active,
        "rate_limit_per_minute": t.rate_limit_per_minute,
        "allowed_sources": t.allowed_sources,
        "has_anthropic_key": bool(t.anthropic_api_key),
        "notes": t.notes,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }
    if include_secret:
        out["api_key"] = t.api_key
    else:
        # Show first 12 chars so admin can identify the tenant by partial key.
        out["api_key_preview"] = t.api_key[:12] + "…" if t.api_key else None
    return out


@router.post("/tenants", status_code=201)
async def admin_create_tenant(
    payload: dict = Body(...),
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    """Create a new tenant. Returns the full api_key ONCE — store it on the
    client side immediately, it can't be retrieved later."""
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    tenant = Tenant(
        name=name,
        anthropic_api_key=payload.get("anthropic_api_key") or None,
        allowed_sources=payload.get("allowed_sources") or None,
        rate_limit_per_minute=int(payload.get("rate_limit_per_minute") or 10),
        notes=payload.get("notes") or None,
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return _tenant_to_dict(tenant, include_secret=True)


@router.get("/tenants")
async def admin_list_tenants(
    include_inactive: bool = Query(False),
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Tenant)
    if not include_inactive:
        stmt = stmt.where(Tenant.active == True)  # noqa: E712
    stmt = stmt.order_by(Tenant.created_at.desc())
    result = await db.execute(stmt)
    tenants = list(result.scalars().all())
    return {"tenants": [_tenant_to_dict(t) for t in tenants], "total": len(tenants)}


@router.get("/tenants/{tenant_id}")
async def admin_get_tenant(
    tenant_id: str,
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    try:
        tid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant_id")
    result = await db.execute(select(Tenant).where(Tenant.id == tid))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return _tenant_to_dict(tenant)


@router.patch("/tenants/{tenant_id}")
async def admin_update_tenant(
    tenant_id: str,
    payload: dict = Body(...),
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    try:
        tid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant_id")
    result = await db.execute(select(Tenant).where(Tenant.id == tid))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    for field in ("name", "anthropic_api_key", "allowed_sources", "rate_limit_per_minute", "active", "notes"):
        if field in payload:
            setattr(tenant, field, payload[field])
    await db.commit()
    await db.refresh(tenant)
    return _tenant_to_dict(tenant)


@router.post("/tenants/{tenant_id}/rotate-key")
async def admin_rotate_tenant_key(
    tenant_id: str,
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    """Issue a new api_key for this tenant. Returns the new key ONCE — the
    old one stops working immediately."""
    try:
        tid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant_id")
    result = await db.execute(select(Tenant).where(Tenant.id == tid))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant.api_key = generate_api_key()
    await db.commit()
    await db.refresh(tenant)
    return _tenant_to_dict(tenant, include_secret=True)


# Anthropic pricing per 1M tokens. Used to estimate per-tenant spend from
# stored token counts. Update when models change. Costs are upper-bound
# estimates — they don't account for prompt caching discounts or batch API.
_MODEL_PRICING = {
    "claude-opus-4-7": {"input": 5.0, "output": 25.0},
    "claude-opus-4-6": {"input": 5.0, "output": 25.0},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
}


def _estimate_cost(model: str | None, tokens_in: int, tokens_out: int) -> float:
    pricing = _MODEL_PRICING.get(model or "", _MODEL_PRICING["claude-opus-4-7"])
    return (tokens_in * pricing["input"] + tokens_out * pricing["output"]) / 1_000_000


@router.get("/tenants/{tenant_id}/usage")
async def admin_tenant_usage(
    tenant_id: str,
    days: int = Query(30, ge=1, le=365),
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    """Per-day token usage and cost estimate for a tenant over the last N days."""
    try:
        tid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant_id")

    tenant = (await db.execute(select(Tenant).where(Tenant.id == tid))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Daily token aggregates. SQLite handles the date() function natively;
    # Postgres needs DATE() cast — both support func.date for our purposes.
    stmt = (
        select(
            func.date(Message.created_at).label("day"),
            Message.model_used,
            func.coalesce(func.sum(Message.tokens_input), 0).label("tokens_in"),
            func.coalesce(func.sum(Message.tokens_output), 0).label("tokens_out"),
            func.count(Message.id).label("messages"),
        )
        .where(Message.tenant_id == tid)
        .where(Message.created_at >= cutoff)
        .where(Message.role == "assistant")
        .group_by(func.date(Message.created_at), Message.model_used)
        .order_by(func.date(Message.created_at).desc())
    )
    rows = (await db.execute(stmt)).all()

    daily: dict[str, dict] = {}
    total_in = total_out = 0
    total_cost = 0.0
    total_messages = 0

    for day, model, t_in, t_out, msg_count in rows:
        cost = _estimate_cost(model, t_in or 0, t_out or 0)
        day_key = str(day)
        if day_key not in daily:
            daily[day_key] = {
                "day": day_key,
                "tokens_in": 0,
                "tokens_out": 0,
                "messages": 0,
                "cost_usd": 0.0,
                "models": {},
            }
        d = daily[day_key]
        d["tokens_in"] += int(t_in or 0)
        d["tokens_out"] += int(t_out or 0)
        d["messages"] += int(msg_count or 0)
        d["cost_usd"] += cost
        if model:
            d["models"][model] = d["models"].get(model, 0) + int(msg_count or 0)

        total_in += int(t_in or 0)
        total_out += int(t_out or 0)
        total_cost += cost
        total_messages += int(msg_count or 0)

    # Round costs for clean JSON.
    for d in daily.values():
        d["cost_usd"] = round(d["cost_usd"], 4)

    return {
        "tenant_id": str(tenant.id),
        "tenant_name": tenant.name,
        "period_days": days,
        "totals": {
            "tokens_in": total_in,
            "tokens_out": total_out,
            "messages": total_messages,
            "cost_usd": round(total_cost, 4),
        },
        "daily": list(daily.values()),
    }


@router.get("/tenants/{tenant_id}/conversations")
async def admin_tenant_conversations(
    tenant_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    """Conversations attributed to a specific tenant. Mirrors the global
    /admin/conversations shape but filtered by tenant_id."""
    from app.models import Conversation, ChatUser
    try:
        tid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant_id")

    # Verify tenant exists.
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tid))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    offset = (page - 1) * per_page

    total_stmt = select(func.count(Conversation.id)).where(Conversation.tenant_id == tid)
    total = (await db.execute(total_stmt)).scalar_one()

    stmt = (
        select(Conversation)
        .where(Conversation.tenant_id == tid)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    rows = list((await db.execute(stmt)).scalars().all())

    return {
        "tenant_id": str(tenant.id),
        "tenant_name": tenant.name,
        "page": page,
        "per_page": per_page,
        "total": total,
        "conversations": [
            {
                "id": str(c.id),
                "title": c.title,
                "language": c.language,
                "message_count": c.message_count,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in rows
        ],
    }


@router.post("/tenants/{tenant_id}/revoke")
async def admin_revoke_tenant(
    tenant_id: str,
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    """Soft-revoke — sets active=False. The tenant's key stops working but
    historical conversations remain accessible."""
    try:
        tid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant_id")
    result = await db.execute(select(Tenant).where(Tenant.id == tid))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant.active = False
    await db.commit()
    return {"id": str(tenant.id), "active": tenant.active}


def _dravya_to_dict(d: Dravya, full: bool = False) -> dict:
    base = {
        "id": str(d.id),
        "nama_sanskrit": d.nama_sanskrit,
        "nama_devanagari": d.nama_devanagari,
        "latin_binomial": d.latin_binomial,
        "family": d.family,
        "english": d.english,
        "hindi": d.hindi,
        "varga_bhavaprakasha": d.varga_bhavaprakasha,
        "rasa": d.rasa,
        "virya": d.virya,
        "vipaka": d.vipaka,
        "review_tier": d.review_tier,
    }
    if not full:
        return base
    return {
        **base,
        "regional_names": d.regional_names,
        "dravya_type": d.dravya_type,
        "varga_other": d.varga_other,
        "part_used": d.part_used,
        "guna": d.guna,
        "prabhava": d.prabhava,
        "dosha_karma": d.dosha_karma,
        "karma": d.karma,
        "prayoga": d.prayoga,
        "matra_value": d.matra_value,
        "matra_unit": d.matra_unit,
        "anupana": d.anupana,
        "kala": d.kala,
        "contraindications": d.contraindications,
        "viruddha": d.viruddha,
        "toxicity_notes": d.toxicity_notes,
        "pregnancy_lactation_status": d.pregnancy_lactation_status,
        "pratinidhi_dravya": d.pratinidhi_dravya,
        "api_monograph_ref": d.api_monograph_ref,
        "nighantu_refs": d.nighantu_refs,
        "imppat_id": d.imppat_id,
        "wikidata_qid": d.wikidata_qid,
        "pubchem_cid": d.pubchem_cid,
        "notes": d.notes,
        "provenance": d.provenance,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@router.get("/dravyas")
async def admin_list_dravyas(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query("", description="Substring match on nama_sanskrit / latin / english / hindi"),
    rasa: str = Query("", description="Filter dravyas containing this rasa"),
    virya: str = Query("", description="Filter by vīrya: uṣṇa or śīta"),
    karma: str = Query("", description="Filter dravyas containing this karma"),
    varga: str = Query("", description="Filter by Bhāvaprakāśa varga"),
    review_tier: str = Query("", description="Filter by review_tier: vaidya|peer|llm-only"),
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    """Browse the materia medica with simple filters."""
    from sqlalchemy import or_

    stmt = select(Dravya)

    if search:
        s = f"%{search}%"
        stmt = stmt.where(
            or_(
                Dravya.nama_sanskrit.ilike(s),
                Dravya.latin_binomial.ilike(s),
                Dravya.english.ilike(s),
                Dravya.hindi.ilike(s),
            )
        )
    if virya:
        stmt = stmt.where(Dravya.virya == virya)
    if varga:
        stmt = stmt.where(Dravya.varga_bhavaprakasha == varga)
    if review_tier:
        stmt = stmt.where(Dravya.review_tier == review_tier)

    stmt = stmt.order_by(Dravya.nama_sanskrit)

    # Total before pagination
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(total_stmt)).scalar_one()

    offset = (page - 1) * per_page
    rows = list((await db.execute(stmt.offset(offset).limit(per_page))).scalars().all())

    # JSON-array filters (rasa, karma) need post-filtering since SQLite stores
    # them as opaque JSON text. Cheap at our scale (≤500 rows).
    if rasa:
        rows = [d for d in rows if d.rasa and rasa in d.rasa]
    if karma:
        rows = [d for d in rows if d.karma and karma in d.karma]

    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "dravyas": [_dravya_to_dict(d) for d in rows],
    }


@router.get("/dravyas/{dravya_id}")
async def admin_get_dravya(
    dravya_id: str,
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    try:
        did = uuid.UUID(dravya_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dravya_id")
    d = (await db.execute(select(Dravya).where(Dravya.id == did))).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Dravya not found")
    return _dravya_to_dict(d, full=True)


@router.get("/dravyas-overview")
async def admin_dravyas_overview(
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate counts for the dashboard."""
    total = (await db.execute(select(func.count(Dravya.id)))).scalar_one()
    by_varga = (await db.execute(
        select(Dravya.varga_bhavaprakasha, func.count(Dravya.id))
        .group_by(Dravya.varga_bhavaprakasha)
    )).all()
    by_review = (await db.execute(
        select(Dravya.review_tier, func.count(Dravya.id))
        .group_by(Dravya.review_tier)
    )).all()
    by_virya = (await db.execute(
        select(Dravya.virya, func.count(Dravya.id))
        .group_by(Dravya.virya)
    )).all()
    return {
        "total": total,
        "by_varga": [{"varga": v or "(unset)", "count": n} for v, n in by_varga],
        "by_review_tier": [{"tier": t or "(unset)", "count": n} for t, n in by_review],
        "by_virya": [{"virya": v or "(unset)", "count": n} for v, n in by_virya],
    }


def _formulation_to_dict(f: Formulation, full: bool = False) -> dict:
    base = {
        "id": str(f.id),
        "name_iast": f.name_iast,
        "name_devanagari": f.name_devanagari,
        "english": f.english,
        "kalpana_type": f.kalpana_type,
        "primary_indication": f.primary_indication,
        "indications": f.indications,
        "review_tier": f.review_tier,
    }
    if not full:
        return base
    return {
        **base,
        "hindi": f.hindi,
        "dosha_action": f.dosha_action,
        "karma": f.karma,
        "dose_value": f.dose_value,
        "dose_unit": f.dose_unit,
        "anupana": f.anupana,
        "kala": f.kala,
        "duration": f.duration,
        "contraindications": f.contraindications,
        "drug_interactions": f.drug_interactions,
        "pregnancy_lactation_status": f.pregnancy_lactation_status,
        "pediatric_status": f.pediatric_status,
        "toxicity_notes": f.toxicity_notes,
        "afi_ref": f.afi_ref,
        "api_ref": f.api_ref,
        "ayush_stg_url": f.ayush_stg_url,
        "shelf_life_days": f.shelf_life_days,
        "method_summary": f.method_summary,
        "classical_source": f.classical_source,
        "classical_chapter": f.classical_chapter,
        "classical_verse": f.classical_verse,
        "notes": f.notes,
        "ingredients": [
            {
                "ingredient_name": ing.ingredient_name,
                "proportion": ing.proportion,
                "role": ing.role,
                "processing": ing.processing,
                "dravya_id": str(ing.dravya_id) if ing.dravya_id else None,
                "position": ing.position,
            }
            for ing in (f.ingredients or [])
        ],
        "provenance": f.provenance,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


@router.get("/formulations")
async def admin_list_formulations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    kalpana_type: str = Query(""),
    indication: str = Query("", description="Substring match against any indication"),
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import or_

    stmt = select(Formulation)
    if search:
        s = f"%{search}%"
        stmt = stmt.where(
            or_(
                Formulation.name_iast.ilike(s),
                Formulation.english.ilike(s),
                Formulation.hindi.ilike(s),
            )
        )
    if kalpana_type:
        stmt = stmt.where(Formulation.kalpana_type == kalpana_type)

    stmt = stmt.order_by(Formulation.kalpana_type, Formulation.name_iast)

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(total_stmt)).scalar_one()

    offset = (page - 1) * per_page
    rows = list((await db.execute(stmt.offset(offset).limit(per_page))).scalars().all())

    if indication:
        ind_lower = indication.lower()
        rows = [
            f for f in rows
            if (f.indications and any(ind_lower in (s or "").lower() for s in f.indications))
            or (f.primary_indication and ind_lower in f.primary_indication.lower())
        ]

    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "formulations": [_formulation_to_dict(f) for f in rows],
    }


@router.get("/formulations/{formulation_id}")
async def admin_get_formulation(
    formulation_id: str,
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.orm import selectinload
    try:
        fid = uuid.UUID(formulation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid formulation_id")
    f = (await db.execute(
        select(Formulation)
        .where(Formulation.id == fid)
        .options(selectinload(Formulation.ingredients))
    )).scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="Formulation not found")
    return _formulation_to_dict(f, full=True)


@router.get("/formulations-overview")
async def admin_formulations_overview(
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    total = (await db.execute(select(func.count(Formulation.id)))).scalar_one()
    by_kalpana = (await db.execute(
        select(Formulation.kalpana_type, func.count(Formulation.id))
        .group_by(Formulation.kalpana_type)
    )).all()
    n_ingredients = (await db.execute(select(func.count(FormulationIngredient.id)))).scalar_one()
    n_resolved = (await db.execute(
        select(func.count(FormulationIngredient.id))
        .where(FormulationIngredient.dravya_id.is_not(None))
    )).scalar_one()
    return {
        "total_formulations": total,
        "by_kalpana_type": [{"type": k or "(unset)", "count": n} for k, n in by_kalpana],
        "ingredients": {"total": n_ingredients, "resolved_to_dravyas": n_resolved},
    }


def _vyadhi_to_dict(v: Vyadhi, full: bool = False) -> dict:
    base = {
        "id": str(v.id),
        "nama_sanskrit": v.nama_sanskrit,
        "nama_devanagari": v.nama_devanagari,
        "english": v.english,
        "hindi": v.hindi,
        "chapter": v.chapter,
        "namaste_code": v.namaste_code,
        "icd11_tm2_code": v.icd11_tm2_code,
        "icd11_main_code": v.icd11_main_code,
        "primary_dosha": v.primary_dosha,
        "review_tier": v.review_tier,
    }
    if not full:
        return base
    return {
        **base,
        "synonyms": v.synonyms,
        "dosha_typology": v.dosha_typology,
        "primary_dushya": v.primary_dushya,
        "srotas": v.srotas,
        "nidana": v.nidana,
        "purva_rupa": v.purva_rupa,
        "rupa": v.rupa,
        "upashaya": v.upashaya,
        "samprapti_summary": v.samprapti_summary,
        "sadhya_asadhya": v.sadhya_asadhya,
        "chikitsa_summary": v.chikitsa_summary,
        "common_formulations": v.common_formulations,
        "common_dravyas": v.common_dravyas,
        "modern_diagnostics": v.modern_diagnostics,
        "red_flags_for_referral": v.red_flags_for_referral,
        "classical_refs": v.classical_refs,
        "ayush_stg_url": v.ayush_stg_url,
        "notes": v.notes,
        "provenance": v.provenance,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


@router.get("/vyadhi")
async def admin_list_vyadhi(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    chapter: str = Query("", description="Filter by classical chapter"),
    primary_dosha: str = Query(""),
    review_tier: str = Query(""),
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import or_

    stmt = select(Vyadhi)
    if search:
        s = f"%{search}%"
        stmt = stmt.where(
            or_(
                Vyadhi.nama_sanskrit.ilike(s),
                Vyadhi.english.ilike(s),
                Vyadhi.hindi.ilike(s),
            )
        )
    if chapter:
        stmt = stmt.where(Vyadhi.chapter == chapter)
    if review_tier:
        stmt = stmt.where(Vyadhi.review_tier == review_tier)

    stmt = stmt.order_by(Vyadhi.chapter, Vyadhi.nama_sanskrit)

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(total_stmt)).scalar_one()

    offset = (page - 1) * per_page
    rows = list((await db.execute(stmt.offset(offset).limit(per_page))).scalars().all())

    if primary_dosha:
        rows = [v for v in rows if v.primary_dosha and primary_dosha.lower() in v.primary_dosha.lower()]

    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "vyadhi": [_vyadhi_to_dict(v) for v in rows],
    }


@router.get("/vyadhi/{vyadhi_id}")
async def admin_get_vyadhi(
    vyadhi_id: str,
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    try:
        vid = uuid.UUID(vyadhi_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid vyadhi_id")
    v = (await db.execute(select(Vyadhi).where(Vyadhi.id == vid))).scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Vyādhi not found")
    return _vyadhi_to_dict(v, full=True)


@router.get("/vyadhi-overview")
async def admin_vyadhi_overview(
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    total = (await db.execute(select(func.count(Vyadhi.id)))).scalar_one()
    by_chapter = (await db.execute(
        select(Vyadhi.chapter, func.count(Vyadhi.id))
        .group_by(Vyadhi.chapter)
    )).all()
    n_with_namaste = (await db.execute(
        select(func.count(Vyadhi.id)).where(Vyadhi.namaste_code.is_not(None))
    )).scalar_one()
    n_with_icd11 = (await db.execute(
        select(func.count(Vyadhi.id)).where(Vyadhi.icd11_main_code.is_not(None))
    )).scalar_one()
    return {
        "total": total,
        "by_chapter": [{"chapter": c or "(unset)", "count": n} for c, n in by_chapter],
        "coding_coverage": {
            "with_namaste_code": n_with_namaste,
            "with_icd11_main_code": n_with_icd11,
        },
    }


# ---- procedures -------------------------------------------------------


def _procedure_to_dict(p: Procedure, full: bool = False) -> dict:
    base = {
        "id": str(p.id),
        "name_iast": p.name_iast,
        "name_devanagari": p.name_devanagari,
        "english": p.english,
        "hindi": p.hindi,
        "category": p.category,
        "subcategory": p.subcategory,
        "practitioner_level": p.practitioner_level,
        "primary_indication": p.primary_indication,
        "review_tier": p.review_tier,
    }
    if not full:
        return base
    return {
        **base,
        "synonyms": p.synonyms,
        "indications": p.indications,
        "dosha_action": p.dosha_action,
        "contraindications": p.contraindications,
        "purva_karma": p.purva_karma,
        "pradhana_karma": p.pradhana_karma,
        "paschat_karma": p.paschat_karma,
        "materials": p.materials,
        "common_oils": p.common_oils,
        "common_dravyas": p.common_dravyas,
        "duration_days": p.duration_days,
        "duration_notes": p.duration_notes,
        "frequency": p.frequency,
        "season": p.season,
        "time_of_day": p.time_of_day,
        "adverse_events": p.adverse_events,
        "pregnancy_lactation_status": p.pregnancy_lactation_status,
        "pediatric_status": p.pediatric_status,
        "geriatric_status": p.geriatric_status,
        "red_flags": p.red_flags,
        "modern_correlate": p.modern_correlate,
        "spa_friendly_version": p.spa_friendly_version,
        "classical_source": p.classical_source,
        "classical_refs": p.classical_refs,
        "afi_ref": p.afi_ref,
        "ayush_stg_url": p.ayush_stg_url,
        "description": p.description,
        "notes": p.notes,
        "provenance": p.provenance,
    }


@router.get("/procedures")
async def admin_list_procedures(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    category: str = Query(""),
    subcategory: str = Query(""),
    practitioner_level: str = Query(""),
    indication: str = Query("", description="Substring match against any indication"),
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import or_

    stmt = select(Procedure)
    if search:
        s = f"%{search}%"
        stmt = stmt.where(
            or_(
                Procedure.name_iast.ilike(s),
                Procedure.english.ilike(s),
                Procedure.hindi.ilike(s),
            )
        )
    if category:
        stmt = stmt.where(Procedure.category == category)
    if subcategory:
        stmt = stmt.where(Procedure.subcategory == subcategory)
    if practitioner_level:
        stmt = stmt.where(Procedure.practitioner_level == practitioner_level)

    stmt = stmt.order_by(Procedure.category, Procedure.name_iast)

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(total_stmt)).scalar_one()

    offset = (page - 1) * per_page
    rows = list(
        (await db.execute(stmt.offset(offset).limit(per_page))).scalars().all()
    )

    if indication:
        ind_lower = indication.lower()
        rows = [
            p for p in rows
            if (p.indications and any(ind_lower in (s or "").lower() for s in p.indications))
            or (p.primary_indication and ind_lower in p.primary_indication.lower())
        ]

    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "procedures": [_procedure_to_dict(p) for p in rows],
    }


@router.get("/procedures/{procedure_id}")
async def admin_get_procedure(
    procedure_id: str,
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    try:
        pid = uuid.UUID(procedure_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid procedure_id")
    p = (await db.execute(
        select(Procedure).where(Procedure.id == pid)
    )).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Procedure not found")
    return _procedure_to_dict(p, full=True)


@router.get("/procedures-overview")
async def admin_procedures_overview(
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    total = (await db.execute(select(func.count(Procedure.id)))).scalar_one()
    by_category = (await db.execute(
        select(Procedure.category, func.count(Procedure.id))
        .group_by(Procedure.category)
    )).all()
    by_practitioner = (await db.execute(
        select(Procedure.practitioner_level, func.count(Procedure.id))
        .group_by(Procedure.practitioner_level)
    )).all()
    return {
        "total": total,
        "by_category": [{"category": c or "(unset)", "count": n} for c, n in by_category],
        "by_practitioner_level": [
            {"level": lvl or "(unset)", "count": n} for lvl, n in by_practitioner
        ],
    }


# ---- parīkṣā (examination + decision tree) ---------------------------


def _param_to_dict(p: ParikshaParam) -> dict:
    return {
        "id": str(p.id),
        "name_iast": p.name_iast,
        "name_devanagari": p.name_devanagari,
        "english": p.english,
        "hindi": p.hindi,
        "schema_family": p.schema_family,
        "domain": p.domain,
        "examination_method": p.examination_method,
        "when_to_examine": p.when_to_examine,
        "findings": p.findings,
        "normal_finding": p.normal_finding,
        "classical_source": p.classical_source,
        "review_tier": p.review_tier,
    }


def _pattern_to_dict(p: DiagnosticPattern) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "description": p.description,
        "pattern_type": p.pattern_type,
        "conditions": p.conditions,
        "targets": p.targets,
        "suggested_chikitsa": p.suggested_chikitsa,
        "red_flags": p.red_flags,
        "evidence_grade": p.evidence_grade,
        "classical_source": p.classical_source,
        "review_tier": p.review_tier,
    }


@router.get("/pariksha/params")
async def admin_list_pariksha_params(
    schema_family: str = Query("", description="Filter by schema_family"),
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ParikshaParam)
    if schema_family:
        stmt = stmt.where(ParikshaParam.schema_family == schema_family)
    stmt = stmt.order_by(ParikshaParam.schema_family, ParikshaParam.name_iast)
    rows = list((await db.execute(stmt)).scalars().all())
    return {
        "total": len(rows),
        "params": [_param_to_dict(p) for p in rows],
    }


@router.get("/pariksha/patterns")
async def admin_list_pariksha_patterns(
    pattern_type: str = Query("", description="Filter by pattern_type (vyadhi | dosha-state | …)"),
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(DiagnosticPattern)
    if pattern_type:
        stmt = stmt.where(DiagnosticPattern.pattern_type == pattern_type)
    stmt = stmt.order_by(DiagnosticPattern.pattern_type, DiagnosticPattern.name)
    rows = list((await db.execute(stmt)).scalars().all())
    return {
        "total": len(rows),
        "patterns": [_pattern_to_dict(p) for p in rows],
    }


@router.post("/pariksha/score")
async def admin_score_pariksha(
    payload: dict = Body(..., description="{findings: [{param, finding}, …]}"),
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    """Run all patterns against the supplied findings and return ranked
    candidates. Findings shape: list of {param: 'Nāḍī', finding: 'vāta-nāḍī'}."""
    findings = payload.get("findings") or []
    if not isinstance(findings, list):
        raise HTTPException(status_code=400, detail="findings must be a list")

    patterns = list(
        (await db.execute(select(DiagnosticPattern))).scalars().all()
    )
    candidates = score_findings(findings, patterns)
    return {
        "findings": findings,
        "patterns_evaluated": len(patterns),
        "candidates": candidates,
    }


@router.get("/pariksha-overview")
async def admin_pariksha_overview(
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    n_params = (await db.execute(select(func.count(ParikshaParam.id)))).scalar_one()
    n_patterns = (await db.execute(select(func.count(DiagnosticPattern.id)))).scalar_one()
    by_schema = (await db.execute(
        select(ParikshaParam.schema_family, func.count(ParikshaParam.id))
        .group_by(ParikshaParam.schema_family)
    )).all()
    by_type = (await db.execute(
        select(DiagnosticPattern.pattern_type, func.count(DiagnosticPattern.id))
        .group_by(DiagnosticPattern.pattern_type)
    )).all()
    return {
        "params": {
            "total": n_params,
            "by_schema_family": [{"family": s or "(unset)", "count": n} for s, n in by_schema],
        },
        "patterns": {
            "total": n_patterns,
            "by_type": [{"type": t or "(unset)", "count": n} for t, n in by_type],
        },
    }


# ---- knowledge graph -------------------------------------------------


@router.get("/kg/neighbors/{kind}/{entity_id}")
async def admin_kg_neighbors(
    kind: str,
    entity_id: str,
    predicate: str = Query("", description="Filter to a single predicate"),
    direction: str = Query("both", description="out | in | both"),
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    """All KG neighbors of one entity, grouped by predicate."""
    try:
        eid = uuid.UUID(entity_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entity_id")
    grouped = await kg_service.neighbors(
        db, kind, eid,
        predicate=predicate or None,
        direction=direction,
    )
    return {"kind": kind, "entity_id": entity_id, "neighbors": grouped}


@router.get("/kg/subgraph/{kind}/{entity_id}")
async def admin_kg_subgraph(
    kind: str,
    entity_id: str,
    depth: int = Query(1, ge=1, le=3),
    predicates: str = Query("", description="Comma-separated predicate filter"),
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    """BFS subgraph around an entity to a given depth (capped at 3)."""
    try:
        eid = uuid.UUID(entity_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entity_id")
    pred_list = [p.strip() for p in predicates.split(",") if p.strip()] or None
    out = await kg_service.subgraph(db, kind, eid, depth=depth, predicates=pred_list)
    return {"kind": kind, "entity_id": entity_id, "depth": depth, **out}


@router.get("/kg-overview")
async def admin_kg_overview(
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    total = (await db.execute(select(func.count(KnowledgeEdge.id)))).scalar_one()
    by_pred = (await db.execute(
        select(KnowledgeEdge.predicate, func.count(KnowledgeEdge.id))
        .group_by(KnowledgeEdge.predicate)
    )).all()
    n_resolved = (await db.execute(
        select(func.count(KnowledgeEdge.id)).where(KnowledgeEdge.target_id.is_not(None))
    )).scalar_one()
    n_unresolved = total - n_resolved

    # Resolution coverage by source kind — useful to find data gaps.
    by_source = (await db.execute(
        select(KnowledgeEdge.source_kind, func.count(KnowledgeEdge.id))
        .group_by(KnowledgeEdge.source_kind)
    )).all()

    return {
        "total_edges": total,
        "resolved_to_uuids": n_resolved,
        "name_only": n_unresolved,
        "by_predicate": [{"predicate": p or "(unset)", "count": n} for p, n in by_pred],
        "by_source_kind": [{"kind": k or "(unset)", "count": n} for k, n in by_source],
    }


# ---- modern evidence (PubMed) -----------------------------------------


def _evidence_to_dict(e: ModernEvidence, full: bool = False) -> dict:
    base = {
        "id": str(e.id),
        "pmid": e.pmid,
        "doi": e.doi,
        "source_db": e.source_db,
        "source_url": e.source_url,
        "title": e.title,
        "journal": e.journal,
        "year": e.year,
        "evidence_tier": e.evidence_tier,
        "dravya_id": str(e.dravya_id) if e.dravya_id else None,
    }
    if not full:
        return base
    return {
        **base,
        "authors": e.authors,
        "pubtypes": e.pubtypes,
        "mesh_terms": e.mesh_terms,
        "abstract_snippet": e.abstract_snippet,
        "indication": e.indication,
        "fetched_at": e.fetched_at.isoformat() if e.fetched_at else None,
        "notes": e.notes,
    }


@router.get("/dravyas/{dravya_id}/evidence")
async def admin_dravya_evidence(
    dravya_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    tier: str = Query("", description="Filter by evidence_tier (A/B/C/D)"),
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    """Modern evidence (PubMed papers) attached to a single dravya."""
    try:
        did = uuid.UUID(dravya_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dravya_id")

    d = (await db.execute(select(Dravya).where(Dravya.id == did))).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Dravya not found")

    stmt = select(ModernEvidence).where(ModernEvidence.dravya_id == did)
    if tier:
        stmt = stmt.where(ModernEvidence.evidence_tier == tier.upper())
    stmt = stmt.order_by(
        ModernEvidence.evidence_tier,
        ModernEvidence.year.desc().nulls_last(),
    )

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(total_stmt)).scalar_one()

    offset = (page - 1) * per_page
    rows = list(
        (await db.execute(stmt.offset(offset).limit(per_page))).scalars().all()
    )

    return {
        "dravya": {
            "id": str(d.id),
            "nama_sanskrit": d.nama_sanskrit,
            "latin_binomial": d.latin_binomial,
        },
        "page": page,
        "per_page": per_page,
        "total": total,
        "evidence": [_evidence_to_dict(e, full=True) for e in rows],
    }


@router.get("/evidence/{evidence_id}")
async def admin_get_evidence(
    evidence_id: str,
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    try:
        eid = uuid.UUID(evidence_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid evidence_id")
    e = (await db.execute(
        select(ModernEvidence).where(ModernEvidence.id == eid)
    )).scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return _evidence_to_dict(e, full=True)


@router.get("/evidence-overview")
async def admin_evidence_overview(
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate counts for the modern-evidence dashboard."""
    total = (await db.execute(select(func.count(ModernEvidence.id)))).scalar_one()
    by_tier = (await db.execute(
        select(ModernEvidence.evidence_tier, func.count(ModernEvidence.id))
        .group_by(ModernEvidence.evidence_tier)
    )).all()
    by_source = (await db.execute(
        select(ModernEvidence.source_db, func.count(ModernEvidence.id))
        .group_by(ModernEvidence.source_db)
    )).all()
    n_dravyas_with_evidence = (await db.execute(
        select(func.count(func.distinct(ModernEvidence.dravya_id)))
    )).scalar_one()
    n_dravyas_total = (await db.execute(select(func.count(Dravya.id)))).scalar_one()

    # Top dravyas by evidence count
    top_stmt = (
        select(
            Dravya.nama_sanskrit,
            Dravya.latin_binomial,
            func.count(ModernEvidence.id).label("n"),
        )
        .join(ModernEvidence, ModernEvidence.dravya_id == Dravya.id)
        .group_by(Dravya.id, Dravya.nama_sanskrit, Dravya.latin_binomial)
        .order_by(func.count(ModernEvidence.id).desc())
        .limit(10)
    )
    top_rows = (await db.execute(top_stmt)).all()

    return {
        "total": total,
        "by_tier": [{"tier": t or "(unset)", "count": n} for t, n in by_tier],
        "by_source": [{"source": s or "(unset)", "count": n} for s, n in by_source],
        "coverage": {
            "dravyas_with_evidence": n_dravyas_with_evidence,
            "dravyas_total": n_dravyas_total,
        },
        "top_dravyas": [
            {"nama_sanskrit": s, "latin_binomial": lb, "count": n}
            for s, lb, n in top_rows
        ],
    }


@router.get("/leads")
async def admin_leads(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    token: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * per_page
    leads = await get_leads(db, limit=per_page, offset=offset)
    return {
        "leads": [
            LeadOut(
                id=str(l.id),
                email=l.email,
                name=l.name,
                source=l.source,
                created_at=l.created_at.isoformat(),
            )
            for l in leads
        ],
        "total": len(leads),
    }
