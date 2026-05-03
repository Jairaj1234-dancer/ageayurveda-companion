from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(prefix="/widget")


@router.get("/config")
async def widget_config():
    settings = get_settings()
    return {
        "name": settings.widget_name,
        "primaryColor": settings.widget_primary_color,
        "accentColor": settings.widget_accent_color,
        "position": settings.widget_position,
        "features": {
            "prakritiQuiz": True,
            "productRecommendations": True,
            "bilingual": True,
            "emailGate": True,
            "emailGateAfter": 3,
            "hardGateAfter": 5,
        },
        "quickActions": [
            {"label_en": "Prakriti Quiz", "label_hi": "प्रकृति परीक्षण", "action": "prakriti"},
            {"label_en": "Digestion", "label_hi": "पाचन", "action": "query", "query": "How can Ayurveda help with digestion?"},
            {"label_en": "Immunity", "label_hi": "रोग प्रतिरोधक", "action": "query", "query": "What does Ayurveda say about building immunity?"},
            {"label_en": "Sleep", "label_hi": "नींद", "action": "query", "query": "Ayurvedic tips for better sleep"},
        ],
    }
