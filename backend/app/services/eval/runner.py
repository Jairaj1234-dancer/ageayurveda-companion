"""Eval runner — execute a benchmark against the live retrieval pipeline.

Loads a benchmark YAML, runs each question through the existing
`app.services.retrieval.retrieve` (zero LLM cost — retrieval-only path
unless the runner is invoked with `with_generation=True`, which is a
future hook, not yet wired).

Outputs:
  - Per-item rows: question, hit@5, mrr, retrieved verse_ids
  - Per-category aggregates
  - Overall scorecard with mean Hit@5 / MRR / nDCG@10 / refusal-correctness

Use: `python -m scripts.run_eval app/data/eval/seed_v1.yaml`
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.eval.benchmark import Benchmark, BenchmarkItem, load_benchmark
from app.services.eval.metrics import (
    hit_at_k,
    mean,
    mean_reciprocal_rank,
    ndcg_at_k,
    recall_at_k,
)
from app.services.retrieval import retrieve


def _verse_id(chunk) -> str:
    """Build the same `source|section|verse_start` key the benchmark uses."""
    return f"{chunk.source}|{chunk.section}|{chunk.verse_start}"


@dataclass
class ItemResult:
    item: BenchmarkItem
    retrieved_ids: list[str]
    hit_at_5: float
    hit_at_10: float
    mrr: float
    recall_at_10: float
    ndcg_at_10: float


@dataclass
class Scorecard:
    benchmark_name: str
    n_items: int
    n_evaluated: int  # may be < n_items if any item has no expected_verses
    n_skipped_safety: int
    overall: dict
    by_category: dict[str, dict]
    items: list[ItemResult] = field(default_factory=list)

    def render(self) -> str:
        lines = []
        lines.append(f"\n{'=' * 70}")
        lines.append(f"  Benchmark: {self.benchmark_name}")
        lines.append(f"  Items: {self.n_items}  (evaluated: {self.n_evaluated}, safety: {self.n_skipped_safety})")
        lines.append(f"{'=' * 70}")
        lines.append("\nOverall (retrieval):")
        for k, v in self.overall.items():
            lines.append(f"  {k:24} {v:.4f}")
        if self.by_category:
            lines.append("\nBy category:")
            for cat, scores in self.by_category.items():
                lines.append(f"  {cat:14}  hit@5={scores.get('hit@5', 0):.3f}  "
                             f"mrr={scores.get('mrr', 0):.3f}  "
                             f"n={scores.get('n', 0)}")
        return "\n".join(lines)


async def run_benchmark(
    db: AsyncSession,
    benchmark: Benchmark,
    *,
    k_for_recall: int = 10,
    strategy: str | None = None,
) -> Scorecard:
    items_by_category: dict[str, list[ItemResult]] = {}
    results: list[ItemResult] = []
    n_evaluated = 0
    n_skipped_safety = 0

    for item in benchmark.items:
        # Safety / should-refuse items don't have a retrieval ground truth;
        # they're evaluated separately when generation is added.
        if item.expected_refusal or not item.expected_verses:
            n_skipped_safety += 1
            continue

        retrievals = await retrieve(db, item.question_en, k=k_for_recall, strategy=strategy)
        retrieved_ids = [_verse_id(r.chunk) for r in retrievals]

        hit5 = hit_at_k(retrieved_ids, item.expected_verses, k=5)
        hit10 = hit_at_k(retrieved_ids, item.expected_verses, k=10)
        mrr = mean_reciprocal_rank(retrieved_ids, item.expected_verses)
        recall10 = recall_at_k(retrieved_ids, item.expected_verses, k=k_for_recall)
        relevance = {v: 1.0 for v in item.expected_verses}
        ndcg10 = ndcg_at_k(retrieved_ids, relevance, k=10)

        ir = ItemResult(
            item=item,
            retrieved_ids=retrieved_ids,
            hit_at_5=hit5,
            hit_at_10=hit10,
            mrr=mrr,
            recall_at_10=recall10,
            ndcg_at_10=ndcg10,
        )
        results.append(ir)
        items_by_category.setdefault(item.category, []).append(ir)
        n_evaluated += 1

    overall = {
        "hit@5": mean(r.hit_at_5 for r in results),
        "hit@10": mean(r.hit_at_10 for r in results),
        "mrr": mean(r.mrr for r in results),
        f"recall@{k_for_recall}": mean(r.recall_at_10 for r in results),
        "ndcg@10": mean(r.ndcg_at_10 for r in results),
    }
    by_category = {
        cat: {
            "n": len(rs),
            "hit@5": mean(r.hit_at_5 for r in rs),
            "mrr": mean(r.mrr for r in rs),
        }
        for cat, rs in items_by_category.items()
    }

    return Scorecard(
        benchmark_name=benchmark.name,
        n_items=benchmark.n_items,
        n_evaluated=n_evaluated,
        n_skipped_safety=n_skipped_safety,
        overall=overall,
        by_category=by_category,
        items=results,
    )


async def run(path: str | Path) -> Scorecard:
    """Convenience wrapper for CLI use — opens its own DB session."""
    from app.database import AsyncSessionLocal

    benchmark = load_benchmark(path)
    async with AsyncSessionLocal() as db:
        return await run_benchmark(db, benchmark)


if __name__ == "__main__":  # pragma: no cover
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "app/data/eval/seed_v1.yaml"
    scorecard = asyncio.run(run(target))
    print(scorecard.render())
