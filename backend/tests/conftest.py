"""Test fixtures.

Each test gets a fresh in-memory SQLite DB so corpus state, message
history, and tenant rows don't leak between tests. The lifespan
auto-create runs against this DB at session setup.
"""
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Force test settings BEFORE app modules import config.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-not-a-real-key")
os.environ.setdefault("APP_ENV", "test")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest_asyncio.fixture
async def db_session():
    """Fresh in-memory SQLite session with all tables created."""
    from app.database import Base
    import app.models  # noqa: F401 — registers all models with Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
        await session.close()
    await engine.dispose()


@pytest.fixture
def stub_embedding(monkeypatch):
    """Replace the heavy sentence-transformers model with a deterministic stub.

    Tests don't care about embedding quality — they care about retrieval
    plumbing. Stub returns a hash-based vector keyed on tokens, so the same
    text gives the same vector and overlapping vocab gives proportional
    cosine similarity.
    """
    import hashlib

    def vec_for(text: str) -> list[float]:
        words = text.lower().split()
        vec = [0.0] * 16
        for word in words:
            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
            for i in range(16):
                vec[i] += ((h >> (i * 4)) & 0xF) / 15.0
        # Normalize.
        n = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / n for v in vec]

    from app.services import embedding as emb_mod

    monkeypatch.setattr(emb_mod, "embed_one", lambda t: vec_for(t))
    monkeypatch.setattr(emb_mod, "embed_many", lambda ts: [vec_for(t) for t in ts])

    # Also stub the retrieval module's reference, since retrieval.py imports
    # embed_one at module load time.
    from app.services import retrieval as ret_mod
    monkeypatch.setattr(ret_mod, "embed_one", lambda t: vec_for(t))

    return vec_for
