"""Side-by-side eval of two embedding models on the seed_v1 benchmark.

Compares baseline (BAAI/bge-m3) vs a fine-tuned candidate (e.g. AyurBGE)
using the existing eval harness. Produces a side-by-side scorecard with
delta highlighting.

Methodology:
  1. Load both models (sentence-transformers).
  2. For each model: re-encode all corpus_chunks in memory (NOT writing
     to DB — purely runtime comparison).
  3. For each benchmark question: dense-retrieve top-K from each model.
  4. Compute Hit@5/Hit@10/MRR/nDCG@10 from the existing metrics module.
  5. Render side-by-side table with deltas.

Pure dense-retrieval comparison — no BM25 / RRF / reranker, so the
score difference is attributable to the embedding model alone.

Usage:
    python -m scripts.compare_eval \\
        --baseline BAAI/bge-m3 \\
        --candidate checkpoints/ayurbge-base-v1

    # For a fast smoke test (subset of corpus):
    python -m scripts.compare_eval --baseline BAAI/bge-m3 \\
        --candidate BAAI/bge-m3 --corpus-limit 500
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

import numpy as np
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import CorpusChunk
from app.services.eval.benchmark import load_benchmark, BenchmarkItem
from app.services.eval.metrics import (
    hit_at_k, mean_reciprocal_rank, ndcg_at_k, mean,
)


def _verse_id(chunk) -> str:
    return f"{chunk.source}|{chunk.section}|{chunk.verse_start}"


def _verse_text_for_embed(chunk) -> str:
    """The text fed into the embedding model — same fields used at
    original ingest so vectors match what production uses."""
    parts = []
    if chunk.sanskrit:
        parts.append(chunk.sanskrit)
    if chunk.transliteration:
        parts.append(chunk.transliteration)
    if chunk.english:
        parts.append(chunk.english)
    if chunk.summary:
        parts.append(chunk.summary)
    return "\n".join(parts)


async def _load_corpus(limit: int | None = None):
    """Pull corpus chunks from DB for in-memory re-encoding."""
    async with AsyncSessionLocal() as db:
        stmt = select(CorpusChunk).order_by(CorpusChunk.created_at)
        if limit:
            stmt = stmt.limit(limit)
        return list((await db.execute(stmt)).scalars().all())


def _evaluate_model(
    model_path: str, model_label: str,
    chunks: list, items: list[BenchmarkItem],
    batch_size: int, top_k: int,
) -> dict:
    """Encode the corpus + each question with the given model, then
    score each question's retrieval against expected_verses."""
    from sentence_transformers import SentenceTransformer

    print(f"\n  {'─' * 60}")
    print(f"  Loading {model_label}: {model_path}")
    t0 = time.monotonic()
    model = SentenceTransformer(model_path)
    print(f"    loaded in {time.monotonic() - t0:.1f}s")

    print(f"  Encoding {len(chunks)} corpus chunks...")
    t0 = time.monotonic()
    corpus_texts = [_verse_text_for_embed(c) for c in chunks]
    corpus_emb = model.encode(
        corpus_texts, convert_to_numpy=True, batch_size=batch_size,
        normalize_embeddings=True, show_progress_bar=False,
    )
    print(f"    encoded in {time.monotonic() - t0:.1f}s — shape {corpus_emb.shape}")

    print(f"  Encoding {len(items)} benchmark questions...")
    queries = [it.question_en for it in items]
    query_emb = model.encode(
        queries, convert_to_numpy=True, normalize_embeddings=True,
        show_progress_bar=False,
    )

    # Compute similarity, get top-K per query
    sims = query_emb @ corpus_emb.T  # shape (n_queries, n_chunks)
    chunk_ids = [_verse_id(c) for c in chunks]

    per_item = []
    hit5_list, hit10_list, mrr_list, ndcg_list = [], [], [], []
    for i, item in enumerate(items):
        if not item.expected_verses or item.expected_refusal:
            continue
        top_idx = np.argpartition(-sims[i], top_k)[:top_k]
        # Sort the top-K by similarity descending
        top_idx = top_idx[np.argsort(-sims[i][top_idx])]
        retrieved_ids = [chunk_ids[j] for j in top_idx]

        h5 = hit_at_k(retrieved_ids, item.expected_verses, k=5)
        h10 = hit_at_k(retrieved_ids, item.expected_verses, k=10)
        mrr = mean_reciprocal_rank(retrieved_ids, item.expected_verses)
        relevance = {v: 1.0 for v in item.expected_verses}
        ndcg = ndcg_at_k(retrieved_ids, relevance, k=10)

        per_item.append({
            "item": item, "retrieved": retrieved_ids,
            "hit@5": h5, "hit@10": h10, "mrr": mrr, "ndcg@10": ndcg,
        })
        hit5_list.append(h5)
        hit10_list.append(h10)
        mrr_list.append(mrr)
        ndcg_list.append(ndcg)

    return {
        "label": model_label,
        "model": model_path,
        "n_evaluated": len(per_item),
        "hit@5": mean(hit5_list),
        "hit@10": mean(hit10_list),
        "mrr": mean(mrr_list),
        "ndcg@10": mean(ndcg_list),
        "per_item": per_item,
    }


def _render_comparison(baseline: dict, candidate: dict) -> str:
    lines = []
    lines.append("\n" + "=" * 78)
    lines.append("  AyurBGE eval comparison — pure dense retrieval (no BM25/RRF)")
    lines.append("=" * 78)
    lines.append(f"  baseline:  {baseline['model']}")
    lines.append(f"  candidate: {candidate['model']}")
    lines.append(f"  evaluated: {baseline['n_evaluated']} items")
    lines.append("")

    headers = ("metric", "baseline", "candidate", "Δ", "Δ%")
    widths = (12, 12, 12, 10, 8)
    fmt = "  " + "  ".join(f"{{:>{w}}}" for w in widths)
    lines.append(fmt.format(*headers))
    lines.append("  " + "  ".join("-" * w for w in widths))

    for metric in ("hit@5", "hit@10", "mrr", "ndcg@10"):
        b = baseline[metric]
        c = candidate[metric]
        delta = c - b
        pct = (delta / b * 100) if b > 0 else float("inf")
        pct_str = f"{pct:+.1f}%" if abs(pct) != float("inf") else "—"
        marker = " ✓" if delta > 0.001 else ("  " if abs(delta) <= 0.001 else " ✗")
        lines.append(fmt.format(
            metric,
            f"{b:.4f}",
            f"{c:.4f}{marker}",
            f"{delta:+.4f}",
            pct_str,
        ))

    lines.append("")
    lines.append("=" * 78)

    # Per-item delta (questions where candidate did better/worse)
    improved = []
    regressed = []
    for b_row, c_row in zip(baseline["per_item"], candidate["per_item"]):
        delta = c_row["hit@5"] - b_row["hit@5"]
        if delta > 0.001:
            improved.append((c_row["item"], delta))
        elif delta < -0.001:
            regressed.append((c_row["item"], delta))

    if improved or regressed:
        lines.append("\n  Per-item delta:")
        if improved:
            lines.append(f"    improved (hit@5 ↑): {len(improved)}")
            for it, d in improved[:5]:
                lines.append(f"      [{it.id}] +{d:.2f}  {it.question_en[:60]}")
        if regressed:
            lines.append(f"    regressed (hit@5 ↓): {len(regressed)}")
            for it, d in regressed[:5]:
                lines.append(f"      [{it.id}] {d:+.2f}  {it.question_en[:60]}")

    return "\n".join(lines)


async def main(args) -> None:
    print("\n  Loading benchmark...")
    bench = load_benchmark(args.benchmark)
    items = [it for it in bench.items if it.expected_verses and not it.expected_refusal]
    print(f"    {len(items)} retrieval items (skipped {bench.n_items - len(items)} safety/refusal)")

    print("\n  Loading corpus...")
    chunks = await _load_corpus(limit=args.corpus_limit)
    print(f"    {len(chunks)} chunks")
    if args.corpus_limit:
        print(f"    (limited to {args.corpus_limit} for fast iteration)")

    baseline = _evaluate_model(
        args.baseline, "baseline", chunks, items,
        batch_size=args.batch_size, top_k=args.top_k,
    )
    candidate = _evaluate_model(
        args.candidate, "candidate", chunks, items,
        batch_size=args.batch_size, top_k=args.top_k,
    )

    print(_render_comparison(baseline, candidate))

    if args.json_out:
        import json
        out = {
            "benchmark": str(args.benchmark),
            "n_evaluated": baseline["n_evaluated"],
            "baseline": {k: baseline[k] for k in ("model", "hit@5", "hit@10", "mrr", "ndcg@10")},
            "candidate": {k: candidate[k] for k in ("model", "hit@5", "hit@10", "mrr", "ndcg@10")},
            "delta": {
                k: candidate[k] - baseline[k]
                for k in ("hit@5", "hit@10", "mrr", "ndcg@10")
            },
        }
        Path(args.json_out).write_text(json.dumps(out, indent=2))
        print(f"\n  JSON scorecard: {args.json_out}")


def _parse_args(argv: list[str] | None = None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--baseline", default="BAAI/bge-m3",
                   help="Baseline embedding model (default BAAI/bge-m3)")
    p.add_argument("--candidate", required=True,
                   help="Candidate model path (e.g. checkpoints/ayurbge-base-v1)")
    p.add_argument("--benchmark", default="app/data/eval/seed_v1.yaml")
    p.add_argument("--corpus-limit", type=int, default=None,
                   help="Limit corpus size for fast iteration (default: full)")
    p.add_argument("--top-k", type=int, default=10,
                   help="Top-K to retrieve per query")
    p.add_argument("--batch-size", type=int, default=32,
                   help="Encoding batch size")
    p.add_argument("--json-out", default=None,
                   help="Optional JSON scorecard output path")
    return p.parse_args(argv)


if __name__ == "__main__":
    asyncio.run(main(_parse_args(sys.argv[1:])))
