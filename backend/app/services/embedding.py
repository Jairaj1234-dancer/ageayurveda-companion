"""Multilingual sentence embeddings used for classical-text retrieval.

Loaded lazily on first use so cold-start of the API is unaffected when
the grounded endpoints aren't being hit. Dimension is fixed by the model
choice in settings; downstream code reads `settings.embedding_dim` rather
than introspecting the model.
"""
from __future__ import annotations

from threading import Lock

from app.config import get_settings
from app.core.logging import logger

_settings = get_settings()
_model = None
_lock = Lock()


def _load_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading embedding model: {_settings.embedding_model}")
                _model = SentenceTransformer(_settings.embedding_model)
                logger.info("Embedding model loaded")
    return _model


def embed_one(text: str) -> list[float]:
    model = _load_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed_many(texts: list[str]) -> list[list[float]]:
    model = _load_model()
    vecs = model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
    return [v.tolist() for v in vecs]
