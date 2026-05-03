from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.lead import LeadCapture, LeadOut
from app.services.conversation import get_or_create_user
from app.services.lead import capture_lead

router = APIRouter(prefix="/leads")


@router.post("/capture", response_model=LeadOut)
async def capture(request: LeadCapture, db: AsyncSession = Depends(get_db)):
    user = await get_or_create_user(db, request.session_id)
    lead = await capture_lead(db, user, request.email, request.name, request.source)
    await db.commit()

    return LeadOut(
        id=str(lead.id),
        email=lead.email,
        name=lead.name,
        source=lead.source,
        created_at=lead.created_at.isoformat(),
    )
