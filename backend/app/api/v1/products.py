from fastapi import APIRouter, Query

from app.schemas.chat import ProductRecommendation
from app.services.product import recommend_products, PRODUCTS

router = APIRouter(prefix="/products")


@router.get("/recommend", response_model=list[ProductRecommendation])
async def get_recommendations(
    query: str = Query("", max_length=500),
    dosha: str | None = Query(None, max_length=20),
):
    if not query and not dosha:
        return []
    results = recommend_products(query, "", dosha=dosha)
    return [ProductRecommendation(**p) for p in results]


@router.get("")
async def list_products():
    return list(PRODUCTS.values())
