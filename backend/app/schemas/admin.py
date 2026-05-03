from pydantic import BaseModel, Field


class AdminLogin(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=255)


class AdminToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DashboardStats(BaseModel):
    total_conversations: int
    total_messages: int
    total_leads: int
    total_prakriti_assessments: int
    conversations_today: int
    api_cost_today: float


class AnalyticsData(BaseModel):
    daily_conversations: list[dict]
    top_queries: list[dict]
    language_distribution: dict
    dosha_distribution: dict
    product_recommendations: list[dict]
