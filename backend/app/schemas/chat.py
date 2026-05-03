from pydantic import BaseModel, Field
from datetime import datetime


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    session_id: str = Field(..., min_length=1, max_length=64)
    language: str = Field(default="auto", max_length=5)
    conversation_id: str | None = None
    sources: list[str] | None = Field(
        default=None,
        description="Restrict grounding to specific classical texts (e.g. ['Charaka Samhita']). None = use all available.",
    )


class Citation(BaseModel):
    source: str
    chapter: str | None = None
    verse: str | None = None
    text: str | None = None


class ProductRecommendation(BaseModel):
    id: str
    name: str
    slug: str
    price: float | None = None
    image_url: str | None = None
    shopify_url: str | None = None
    dosha_balance: str | None = None
    score: float


class ChatResponse(BaseModel):
    message: str
    conversation_id: str
    citations: list[Citation] = []
    products: list[ProductRecommendation] = []
    disclaimer: str | None = None
    language: str = "en"


class StreamEvent(BaseModel):
    type: str  # "token", "done", "error"
    content: str | None = None
    citations: list[Citation] | None = None
    products: list[ProductRecommendation] | None = None
    disclaimer: str | None = None
    conversation_id: str | None = None


class ConversationHistory(BaseModel):
    conversation_id: str
    title: str | None = None
    messages: list["MessageOut"]
    created_at: datetime


class MessageOut(BaseModel):
    role: str
    content: str
    citations: list[Citation] = []
    products: list[ProductRecommendation] = []
    disclaimer: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
