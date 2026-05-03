from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.prakriti import PrakritiQuestion, PrakritiSubmission, PrakritiResultOut, DoshaScore
from app.services.prakriti import load_questions, score_prakriti, get_recommendations
from app.services.conversation import get_or_create_user
from app.services.product import recommend_products
from app.models.prakriti_result import PrakritiResult

router = APIRouter(prefix="/prakriti")


@router.get("/questions", response_model=list[PrakritiQuestion])
async def get_questions():
    questions = load_questions()
    return questions


@router.post("/submit", response_model=PrakritiResultOut)
async def submit_prakriti(
    submission: PrakritiSubmission,
    db: AsyncSession = Depends(get_db),
):
    user = await get_or_create_user(db, submission.session_id, submission.language)

    result = score_prakriti(submission.answers)
    recs = get_recommendations(result["constitution"])

    # Get product recommendations for this dosha
    product_recs = recommend_products(
        result["constitution"],
        " ".join(recs.get("diet", [])),
        dosha=result["constitution"],
    )
    product_slugs = [p["slug"] for p in product_recs]

    # Save result
    prakriti_result = PrakritiResult(
        user_id=user.id,
        constitution=result["constitution"],
        scores=result["scores"],
        answers=submission.answers,
        recommendations={"diet": recs["diet"], "lifestyle": recs["lifestyle"], "products": product_slugs},
        language=submission.language,
    )
    db.add(prakriti_result)
    await db.commit()

    description = recs.get("description", {})

    return PrakritiResultOut(
        constitution=result["constitution"],
        scores=DoshaScore(**result["scores"]),
        description_en=description.get("en", ""),
        description_hi=description.get("hi", ""),
        diet=recs["diet"],
        lifestyle=recs["lifestyle"],
        products=product_slugs,
    )
