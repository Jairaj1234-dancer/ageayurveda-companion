"""Retrieve top-K classical-text chunks for a query.

Two strategies:

  - "dense":  cosine similarity over sentence-transformers embeddings.
              Strong on conceptual / paraphrased queries.
  - "hybrid": dense + BM25 lexical, fused via Reciprocal Rank Fusion.
              Default. Better on Sanskrit terms, herb names, and exact
              verse references that pure semantic embeddings can miss.

Both strategies load the corpus into memory and rank in Python — fine up
to ~100K chunks. Past that, swap dense for pgvector and BM25 for Postgres
FTS or a precomputed inverted index, keeping the same return shape.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import logger
from app.models import CorpusChunk
from app.services.bm25 import bm25_scores, reciprocal_rank_fusion
from app.services.embedding import embed_one
from app.services import reranker as reranker_mod


_settings = get_settings()


@dataclass
class Retrieval:
    chunk: CorpusChunk
    score: float
    dense_score: float | None = None
    bm25_score: float | None = None
    rerank_score: float | None = None


def _dense_rank(query: str, chunks: list[CorpusChunk]) -> list[float]:
    """Cosine similarity (assuming normalized vectors) between query and each
    chunk. During an embedding-model migration the corpus may contain rows
    embedded under different models with different dimensions — chunks whose
    dim doesn't match the query's are scored as 0 so they sink in dense
    ranking but are still recoverable via BM25.
    """
    query_vec = np.asarray(embed_one(query), dtype=np.float32)
    qdim = query_vec.shape[0]
    scores = []
    for c in chunks:
        vec = c.embedding or []
        if len(vec) != qdim:
            scores.append(0.0)
            continue
        scores.append(float(np.dot(np.asarray(vec, dtype=np.float32), query_vec)))
    return scores


def _bm25_corpus_text(chunk: CorpusChunk) -> str:
    """Document text used for BM25 — combine all retrievable surface forms
    so that a query in Sanskrit, transliteration, or English all find the
    same chunk.
    """
    parts = [
        chunk.sanskrit or "",
        chunk.transliteration or "",
        chunk.english or "",
        chunk.summary or "",
    ]
    return " ".join(p for p in parts if p)


async def retrieve(
    db: AsyncSession,
    query: str,
    k: int | None = None,
    sources: Sequence[str] | None = None,
    strategy: str | None = None,
) -> list[Retrieval]:
    if not query.strip():
        return []

    k = k or _settings.retrieval_top_k
    strategy = strategy or _settings.retrieval_strategy

    stmt = select(CorpusChunk)
    if sources:
        stmt = stmt.where(CorpusChunk.source.in_(list(sources)))
    result = await db.execute(stmt)
    chunks: list[CorpusChunk] = list(result.scalars().all())
    if not chunks:
        return []

    dense_scores = _dense_rank(query, chunks)

    if strategy == "dense":
        order = np.argsort(-np.asarray(dense_scores))[:k]
        return [
            Retrieval(chunk=chunks[i], score=float(dense_scores[i]), dense_score=float(dense_scores[i]))
            for i in order
        ]

    # Hybrid: BM25 + dense, fused via RRF.
    docs = [_bm25_corpus_text(c) for c in chunks]
    lex_scores = bm25_scores(query, docs)

    n = len(chunks)
    dense_pool = min(_settings.retrieval_dense_pool, n)
    bm25_pool = min(_settings.retrieval_bm25_pool, n)

    dense_order = list(np.argsort(-np.asarray(dense_scores))[:dense_pool])
    bm25_order = sorted(range(n), key=lambda i: -lex_scores[i])[:bm25_pool]
    bm25_order = [i for i in bm25_order if lex_scores[i] > 0]  # drop zero-score noise

    fused = reciprocal_rank_fusion([dense_order, bm25_order])
    if not fused:
        # No BM25 hits at all — fall through to dense-only ranking.
        order = np.argsort(-np.asarray(dense_scores))[:k]
        return [
            Retrieval(chunk=chunks[i], score=float(dense_scores[i]), dense_score=float(dense_scores[i]))
            for i in order
        ]

    # If a reranker is configured, take a larger fused candidate pool and
    # cross-encode each (query, candidate) pair, then return the top K
    # by reranker score. Otherwise return the top K by fused score.
    if reranker_mod.is_enabled():
        rerank_pool = min(_settings.retrieval_rerank_pool, len(fused))
        candidates = sorted(fused.items(), key=lambda kv: -kv[1])[:rerank_pool]
        candidate_idxs = [idx for idx, _ in candidates]
        candidate_texts = [_bm25_corpus_text(chunks[i]) for i in candidate_idxs]
        rerank_scores = reranker_mod.rerank(query, candidate_texts)
        # Sort by rerank score, descending
        ordered = sorted(
            zip(candidate_idxs, rerank_scores), key=lambda p: -p[1]
        )[:k]
        return [
            Retrieval(
                chunk=chunks[idx],
                score=float(rerank_score),
                dense_score=float(dense_scores[idx]),
                bm25_score=float(lex_scores[idx]),
                rerank_score=float(rerank_score),
            )
            for idx, rerank_score in ordered
        ]

    top = sorted(fused.items(), key=lambda kv: -kv[1])[:k]
    out: list[Retrieval] = []
    for idx, fused_score in top:
        out.append(Retrieval(
            chunk=chunks[idx],
            score=float(fused_score),
            dense_score=float(dense_scores[idx]),
            bm25_score=float(lex_scores[idx]),
        ))
    return out
