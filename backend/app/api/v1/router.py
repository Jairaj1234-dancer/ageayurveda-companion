from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.chat import router as chat_router
from app.api.v1.prakriti import router as prakriti_router
from app.api.v1.products import router as products_router
from app.api.v1.leads import router as leads_router
from app.api.v1.widget import router as widget_router
from app.api.v1.admin import router as admin_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(chat_router, tags=["chat"])
api_router.include_router(prakriti_router, tags=["prakriti"])
api_router.include_router(products_router, tags=["products"])
api_router.include_router(leads_router, tags=["leads"])
api_router.include_router(widget_router, tags=["widget"])
api_router.include_router(admin_router, tags=["admin"])
