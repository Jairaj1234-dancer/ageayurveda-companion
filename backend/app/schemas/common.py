from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None
