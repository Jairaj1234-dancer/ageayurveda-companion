"""Optional stage-2 cross-encoder reranker for retrieval.

When `settings.retrieval_reranker_model` is set, retrieval inflates the
candidate pool (via `retrieval_rerank_pool`) and runs a cross-encoder
to score each (query, candidate) pair, then takes the top K.

Recommended models, in order of quality vs. resource cost:
  - BAAI/bge-reranker-v2-m3       (568M, multilingual incl. Hindi/Sanskrit)
  - BAAI/bge-reranker-base        (110M, English-leaning, smaller)
  - cross-encoder/ms-marco-MiniLM-L-6-v2  (22M, English-only, very small)

No LLM API cost — local inference only. First call lazy-loads the model
into a module-level singleton.
"""
from __future__ import annotations

from threading import Lock

from app.config import get_settings
from app.core.logging import logger

_settings = get_settings()
_model = None
_lock = Lock()


def is_enabled() -> bool:
    return bool(_settings.retrieval_reranker_model)


def _load():
    global _model
    if _model is not None or not is_enabled():
        return _model
    with _lock:
        if _model is None:
            from sentence_transformers import CrossEncoder

            logger.info("Loading reranker: %s", _settings.retrieval_reranker_model)
            _model = CrossEncoder(
                _settings.retrieval_reranker_model,
                trust_remote_code=False,
                max_length=512,
            )
            logger.info("Reranker loaded")
    return _model


def rerank(query: str, candidates: list[str]) -> list[float]:
    """Score each candidate against the query. Returns scores in input order.

    Empty when reranker is disabled — callers should fall back to existing
    fused scores in that case.
    """
    if not is_enabled() or not candidates:
        return []
    model = _load()
    pairs = [(query, c) for c in candidates]
    raw = model.predict(pairs, batch_size=32, show_progress_bar=False)
    return [float(x) for x in raw]
