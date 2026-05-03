from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    app_name: str = "AgeAyurveda Companion"
    app_env: str = "development"
    debug: bool = False
    secret_key: str = "change-me-in-production"
    api_v1_prefix: str = "/api/v1"

    # Database (SQLite for local dev, PostgreSQL for production)
    database_url: str = "sqlite+aiosqlite:///./ageayurveda.db"

    conversation_history_limit: int = 6

    # Classical-text grounding (Phase 1 of platform pivot)
    anthropic_api_key: str = ""
    grounded_model: str = "claude-opus-4-7"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    retrieval_top_k: int = 6
    retrieval_strategy: str = "hybrid"  # "dense" | "hybrid"
    retrieval_dense_pool: int = 20  # candidates from dense before RRF fusion
    retrieval_bm25_pool: int = 20  # candidates from BM25 before RRF fusion
    # Optional stage-2 cross-encoder reranker. When set to a HuggingFace
    # model id (e.g. "BAAI/bge-reranker-v2-m3" or "BAAI/bge-reranker-base"),
    # retrieve enlarges the candidate pool to retrieval_rerank_pool, then
    # cross-encoder-reranks down to retrieval_top_k. Empty = disabled.
    retrieval_reranker_model: str = ""
    retrieval_rerank_pool: int = 30
    grounded_max_tokens: int = 2048
    rate_limit_grounded: str = "10/minute"

    # CORS
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    # Admin JWT
    admin_jwt_algorithm: str = "HS256"
    admin_jwt_expiry_minutes: int = 30

    # Rate limiting
    rate_limit_chat: str = "20/minute"
    rate_limit_prakriti: str = "5/minute"
    rate_limit_read: str = "60/minute"

    # Widget
    widget_name: str = "Ayurveda Guide"
    widget_primary_color: str = "#2E7D32"
    widget_accent_color: str = "#FF8F00"
    widget_position: str = "bottom-right"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
