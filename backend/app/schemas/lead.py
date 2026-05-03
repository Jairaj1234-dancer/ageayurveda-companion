from pydantic import BaseModel, Field, EmailStr


class LeadCapture(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    email: str = Field(..., min_length=5, max_length=255)
    name: str | None = Field(default=None, max_length=255)
    source: str = Field(default="chat_widget", max_length=50)


class LeadOut(BaseModel):
    id: str
    email: str
    name: str | None
    source: str
    created_at: str

    model_config = {"from_attributes": True}
