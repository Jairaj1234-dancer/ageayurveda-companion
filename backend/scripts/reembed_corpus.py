"""Re-embed corpus chunks under a new embedding model.

Selects rows whose `embedding_model` differs from `settings.embedding_model`,
re-embeds them in batches, and writes back the new vector + new model tag.
Idempotent: re-running stops once every row matches the current setting.

Why selectivity matters: the corpus is 20K+ rows and bge-m3 inference is
~3× slower than MiniLM, so a single sweep takes 30+ minutes on CPU.
Re-runs after a partial failure can resume cleanly.

Usage:
    python -m scripts.reembed_corpus                  # all stale rows
    python -m scripts.reembed_corpus --limit 100      # smoke test
    python -m scripts.reembed_corpus --batch-size 64
    python -m scripts.reembed_corpus --dry-run        # report only
    python -m scripts.reembed_corpus --target-model BAAI/bge-m3
                                                       # override settings
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from typing import Iterable

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal, Base, engine
from app.models import CorpusChunk  # noqa: F401 — registers all models
from app.services import embedding as embedding_service


def _embed_text_for_chunk(c: CorpusChunk) -> str:
    """Concatenate the same fields used at original ingest time so the
    new vectors live in a comparable semantic space."""
    parts = []
    if c.sanskrit:
        parts.append(c.sanskrit)
    if c.transliteration:
        parts.append(c.transliteration)
    if c.english:
        parts.append(c.english)
    if c.summary:
        parts.append(c.summary)
    return "\n".join(parts) or c.citation_label()


async def _count_stale(db: AsyncSession, target_model: str) -> int:
    return (await db.execute(
        select(func.count(CorpusChunk.id))
        .where(CorpusChunk.embedding_model != target_model)
    )).scalar_one()


async def _select_stale(
    db: AsyncSession, target_model: str, limit: int | None
) -> list[CorpusChunk]:
    stmt = (
        select(CorpusChunk)
        .where(CorpusChunk.embedding_model != target_model)
        .order_by(CorpusChunk.created_at)
    )
    if limit:
        stmt = stmt.limit(limit)
    return list((await db.execute(stmt)).scalars().all())


async def reembed_batch(
    db: AsyncSession, chunks: list[CorpusChunk], target_model: str
) -> int:
    """Compute new vectors for one batch and write them back. Caller commits."""
    if not chunks:
        return 0
    texts = [_embed_text_for_chunk(c) for c in chunks]
    vectors = embedding_service.embed_many(texts)
    for c, v in zip(chunks, vectors):
        c.embedding = v
        c.embedding_model = target_model
    return len(chunks)


async def main(args) -> None:
    settings = get_settings()
    target_model = args.target_model or settings.embedding_model

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        stale_total = await _count_stale(db, target_model)
        total_rows = (await db.execute(select(func.count(CorpusChunk.id)))).scalar_one()

    print(f"Re-embedding under {target_model}")
    print(f"  total chunks: {total_rows}")
    print(f"  stale chunks: {stale_total}")
    print(f"  batch size:   {args.batch_size}")
    print(f"  dry_run:      {args.dry_run}")

    if stale_total == 0:
        print("\nNothing to do — all chunks already embedded under the target model.")
        return

    if args.dry_run:
        print("\n(dry-run) Would re-embed", min(stale_total, args.limit or stale_total), "rows.")
        return

    started = time.monotonic()
    processed = 0
    target_n = args.limit or stale_total

    while processed < target_n:
        async with AsyncSessionLocal() as db:
            remaining = target_n - processed
            batch_limit = min(args.batch_size, remaining)
            chunks = await _select_stale(db, target_model, limit=batch_limit)
            if not chunks:
                break

            n = await reembed_batch(db, chunks, target_model)
            await db.commit()
            processed += n

            elapsed = time.monotonic() - started
            rate = processed / elapsed if elapsed > 0 else 0.0
            eta = (target_n - processed) / rate if rate > 0 else 0.0
            print(
                f"  [{processed}/{target_n}] +{n} "
                f"elapsed={elapsed:.0f}s rate={rate:.1f}/s eta={eta:.0f}s"
            )

    elapsed = time.monotonic() - started
    print(f"\nDone in {elapsed:.0f}s. Re-embedded {processed} rows.")

    async with AsyncSessionLocal() as db:
        remaining_stale = await _count_stale(db, target_model)
    print(f"Remaining stale: {remaining_stale}")


def _parse_args(argv: Iterable[str] | None = None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limit", type=int, default=None,
                   help="Process at most N stale rows (debug)")
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--dry-run", action="store_true",
                   help="Report counts but don't run inference or write")
    p.add_argument("--target-model", type=str, default=None,
                   help="Override settings.embedding_model for this run")
    return p.parse_args(argv)


if __name__ == "__main__":
    asyncio.run(main(_parse_args(sys.argv[1:])))
