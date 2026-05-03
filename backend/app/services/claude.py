"""
Chat response generator using rule-based static responses.
"""

from collections.abc import AsyncGenerator

from app.services.static_chat import get_static_response
from app.core.logging import logger

GREETING_PATTERNS = [
    "hello", "hi", "hey", "namaste", "namaskar", "good morning",
    "good afternoon", "good evening", "नमस्ते", "नमस्कार",
]

GREETING_RESPONSE = {
    "en": "Namaste! 🙏 I'm your Ayurveda Guide, here to help you discover your Prakriti and find the right Ayurvedic products.\n\nI can help you with:\n• Understanding Ayurvedic concepts and doshas\n• Discovering your Prakriti (body constitution)\n• Finding Age Ayurveda products suited for you\n• Digestive health, immunity, sleep, skin care & more\n\nHow can I assist you today?",
    "hi": "नमस्ते! 🙏 मैं आपका आयुर्वेद गाइड हूं, आपकी प्रकृति जानने और सही आयुर्वेदिक उत्पाद खोजने में मदद के लिए।\n\nमैं आपकी इन विषयों में सहायता कर सकता हूं:\n• आयुर्वेदिक अवधारणाओं और दोषों को समझना\n• आपकी प्रकृति (शरीर संविधान) जानना\n• आपके लिए उपयुक्त Age Ayurveda उत्पाद खोजना\n• पाचन, रोग प्रतिरोधक क्षमता, नींद, त्वचा देखभाल और बहुत कुछ\n\nमैं आज आपकी कैसे सहायता कर सकता हूं?",
}


def is_greeting(text: str) -> bool:
    text_lower = text.lower().strip()
    return any(text_lower.startswith(g) or text_lower == g for g in GREETING_PATTERNS)


async def generate_response(
    user_message: str,
    context_chunks: list[dict] | None = None,
    history: list[dict] | None = None,
    language: str = "en",
) -> dict:
    """Generate a response using the static rule-based engine."""
    if is_greeting(user_message):
        return {
            "content": GREETING_RESPONSE.get(language, GREETING_RESPONSE["en"]),
            "model": "static",
            "tokens_input": 0,
            "tokens_output": 0,
        }

    static = get_static_response(user_message, language)
    return {
        "content": static["content"],
        "model": static["model"],
        "tokens_input": 0,
        "tokens_output": 0,
        "products": static.get("products", []),
    }


async def generate_stream(
    user_message: str,
    context_chunks: list[dict] | None = None,
    history: list[dict] | None = None,
    language: str = "en",
) -> AsyncGenerator[dict, None]:
    """Generate a streaming response using the static engine."""
    if is_greeting(user_message):
        content = GREETING_RESPONSE.get(language, GREETING_RESPONSE["en"])
        for word in content.split(" "):
            yield {"type": "token", "content": word + " "}
        yield {"type": "done", "content": content, "model": "static", "tokens_input": 0, "tokens_output": 0}
        return

    static = get_static_response(user_message, language)
    content = static["content"]
    for word in content.split(" "):
        yield {"type": "token", "content": word + " "}
    yield {
        "type": "done",
        "content": content,
        "model": static["model"],
        "tokens_input": 0,
        "tokens_output": 0,
        "products": static.get("products", []),
    }
