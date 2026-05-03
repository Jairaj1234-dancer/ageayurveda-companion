"""Ingest classical-text YAML files into the corpus_chunks table.

Each YAML file describes one source/section and contains a list of verses.
For each verse we build a single retrieval text (Sanskrit + transliteration +
English + summary), embed it, and write a row to corpus_chunks.

Reingesting the same file is safe: existing rows from that source/section
are deleted before insertion, so corpus updates are simple file edits + rerun.

Usage:
    python -m scripts.ingest_corpus app/data/corpus/ashtanga_hridaya_sutrasthana.yaml
    python -m scripts.ingest_corpus app/data/corpus/   # all .yaml in dir
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import yaml
from sqlalchemy import delete, select, func

from app.config import get_settings
from app.database import AsyncSessionLocal, engine, Base
from app.models import CorpusChunk  # noqa: F401 — registers model
from app.services.embedding import embed_many


def _build_text(verse: dict) -> str:
    parts = []
    if verse.get("sanskrit"):
        parts.append(verse["sanskrit"])
    if verse.get("transliteration"):
        parts.append(verse["transliteration"])
    if verse.get("english"):
        parts.append(verse["english"])
    if verse.get("summary"):
        parts.append(verse["summary"])
    return "\n".join(parts)


async def _ingest_file(path: Path) -> int:
    settings = get_settings()
    print(f"Loading {path}")
    with open(path) as f:
        doc = yaml.safe_load(f)

    source = doc["source"]
    section = doc.get("section")
    license_str = doc.get("license")
    verses = doc["verses"]

    texts = [_build_text(v) for v in verses]
    print(f"Embedding {len(texts)} verses with {settings.embedding_model}...")
    embeddings = embed_many(texts)

    async with AsyncSessionLocal() as db:
        await db.execute(
            delete(CorpusChunk).where(
                CorpusChunk.source == source,
                CorpusChunk.section == section,
            )
        )

        for verse, vec in zip(verses, embeddings):
            chunk = CorpusChunk(
                source=source,
                section=section,
                chapter=verse.get("chapter"),
                verse_start=verse.get("verse_start"),
                verse_end=verse.get("verse_end"),
                sanskrit=verse.get("sanskrit"),
                transliteration=verse.get("transliteration"),
                english=verse.get("english"),
                summary=verse.get("summary"),
                license=license_str,
                embedding=vec,
                embedding_model=settings.embedding_model,
                token_count=len(_build_text(verse).split()),
            )
            db.add(chunk)

        await db.commit()

    return len(verses)


async def _ensure_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def main(targets: list[str]):
    await _ensure_tables()

    paths: list[Path] = []
    for t in targets:
        p = Path(t)
        if p.is_dir():
            paths.extend(sorted(p.glob("*.yaml")))
        else:
            paths.append(p)

    if not paths:
        print("No YAML files found.")
        return

    total = 0
    for p in paths:
        total += await _ingest_file(p)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(func.count(CorpusChunk.id)))
        count = result.scalar_one()
    print(f"Done. Ingested {total} verses this run. Total in corpus: {count}")


if __name__ == "__main__":
    targets = sys.argv[1:] or ["app/data/corpus/"]
    asyncio.run(main(targets))
