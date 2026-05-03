"""Build (anchor, positive) training pairs for AyurBGE fine-tuning.

Zero LLM cost. Runs on CPU in seconds. Reads the existing
data layers (CorpusChunk + Dravya + Formulation + Vyadhi + Procedure +
DiagnosticPattern) and emits a JSONL dataset suitable for
sentence-transformers' MultipleNegativesRankingLoss.

Pair sources (all deterministic, classically-grounded):

  1. Cross-script verse pairs — (Sanskrit-Devanagari, IAST) for the
     same verse. Trains script-invariance.

  2. Verse ↔ chapter-context pairs — (verse, chapter-prefix-context).
     Trains within-text coherence.

  3. Concept-name pairs — (English term, Sanskrit name) from rows
     where both fields exist. Strong domain alignment signal.

  4. Diagnostic-pattern context pairs — (pattern-description,
     target-vyadhi-name) from DiagnosticPattern rows.

  5. Indication ↔ formulation pairs.

  6. Hindi ↔ Sanskrit pairs.

Output: app/data/finetune/pairs_v1.jsonl
Each line: {"anchor": "...", "positive": "...", "source": "...", "lang_a": "...", "lang_b": "..."}

Usage:
    python -m scripts.build_finetune_pairs
    python -m scripts.build_finetune_pairs --output app/data/finetune/pairs_v2.jsonl
    python -m scripts.build_finetune_pairs --max-per-source 5000
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, Base, engine
from app.models import (
    CorpusChunk, Dravya, Formulation, Vyadhi, Procedure,
    DiagnosticPattern,
)


DEFAULT_OUTPUT = Path("app/data/finetune/pairs_v1.jsonl")


def _emit(out, anchor: str, positive: str, source: str, lang_a: str, lang_b: str) -> int:
    """Append one pair to the JSONL file. Returns 1 if written, 0 if skipped."""
    if not anchor or not positive:
        return 0
    a = anchor.strip()
    p = positive.strip()
    if not a or not p or a == p:
        return 0
    out.write(json.dumps({
        "anchor": a, "positive": p,
        "source": source,
        "lang_a": lang_a, "lang_b": lang_b,
    }, ensure_ascii=False) + "\n")
    return 1


# ---- Source 1: Cross-script verse pairs ------------------------------


async def emit_cross_script_pairs(
    db: AsyncSession, out, max_n: int | None
) -> int:
    """For each verse with both Sanskrit and IAST, emit (sanskrit, iast)."""
    rows = (await db.execute(
        select(CorpusChunk.sanskrit, CorpusChunk.transliteration)
        .where(CorpusChunk.sanskrit.is_not(None))
        .where(CorpusChunk.transliteration.is_not(None))
    )).all()
    n = 0
    for sanskrit, iast in rows:
        if max_n and n >= max_n:
            break
        n += _emit(out, sanskrit, iast, "cross-script-verse", "sa-deva", "sa-iast")
    return n


# ---- Source 2: Verse ↔ chapter-context pairs --------------------------


async def emit_verse_context_pairs(
    db: AsyncSession, out, max_n: int | None
) -> int:
    """For each verse, build a chapter-context label and emit
    (verse, context-label) so embedding learns within-text coherence.
    """
    rows = (await db.execute(
        select(CorpusChunk.transliteration, CorpusChunk.source,
               CorpusChunk.section, CorpusChunk.chapter)
        .where(CorpusChunk.transliteration.is_not(None))
    )).all()
    n = 0
    for iast, src, section, chapter in rows:
        if max_n and n >= max_n:
            break
        ctx_parts = [p for p in (src, section, chapter) if p]
        if len(ctx_parts) < 2:
            continue
        context = " — ".join(ctx_parts)
        n += _emit(out, iast, context, "verse-context", "sa-iast", "en-context")
    return n


# ---- Source 3: Concept-name pairs (Dravya) ----------------------------


async def emit_dravya_pairs(db: AsyncSession, out, max_n: int | None) -> int:
    rows = (await db.execute(select(Dravya))).scalars().all()
    n = 0
    for d in rows:
        if max_n and n >= max_n:
            break
        # English ↔ Sanskrit
        if d.english and d.nama_sanskrit:
            n += _emit(out, d.english, d.nama_sanskrit,
                       "dravya-en-sa", "en", "sa-iast")
        # Latin binomial ↔ Sanskrit
        if d.latin_binomial and d.nama_sanskrit:
            n += _emit(out, d.latin_binomial, d.nama_sanskrit,
                       "dravya-latin-sa", "la", "sa-iast")
        # Hindi ↔ Sanskrit
        if d.hindi and d.nama_sanskrit:
            n += _emit(out, d.hindi, d.nama_sanskrit,
                       "dravya-hi-sa", "hi", "sa-iast")
        # Devanagari ↔ IAST same dravya
        if d.nama_devanagari and d.nama_sanskrit:
            n += _emit(out, d.nama_devanagari, d.nama_sanskrit,
                       "dravya-deva-iast", "sa-deva", "sa-iast")
    return n


# ---- Source 4: Concept-name pairs (Formulation) -----------------------


async def emit_formulation_pairs(db: AsyncSession, out, max_n: int | None) -> int:
    rows = (await db.execute(select(Formulation))).scalars().all()
    n = 0
    for f in rows:
        if max_n and n >= max_n:
            break
        if f.english and f.name_iast:
            n += _emit(out, f.english, f.name_iast,
                       "formulation-en-iast", "en", "sa-iast")
        if f.hindi and f.name_iast:
            n += _emit(out, f.hindi, f.name_iast,
                       "formulation-hi-iast", "hi", "sa-iast")
        # Indication ↔ formulation
        if f.indications and f.name_iast:
            for ind in f.indications:
                if max_n and n >= max_n:
                    break
                n += _emit(out, ind, f.name_iast,
                           "indication-formulation", "mixed", "sa-iast")
        if f.primary_indication and f.name_iast:
            n += _emit(out, f.primary_indication, f.name_iast,
                       "primary-ind-formulation", "en", "sa-iast")
    return n


# ---- Source 5: Concept-name pairs (Vyādhi) ----------------------------


async def emit_vyadhi_pairs(db: AsyncSession, out, max_n: int | None) -> int:
    rows = (await db.execute(select(Vyadhi))).scalars().all()
    n = 0
    for v in rows:
        if max_n and n >= max_n:
            break
        if v.english and v.nama_sanskrit:
            n += _emit(out, v.english, v.nama_sanskrit,
                       "vyadhi-en-sa", "en", "sa-iast")
        if v.hindi and v.nama_sanskrit:
            n += _emit(out, v.hindi, v.nama_sanskrit,
                       "vyadhi-hi-sa", "hi", "sa-iast")
        # Symptom-set ↔ vyādhi
        if v.rupa and v.nama_sanskrit:
            for symptom in v.rupa:
                if max_n and n >= max_n:
                    break
                n += _emit(out, symptom, v.nama_sanskrit,
                           "rupa-vyadhi", "en", "sa-iast")
    return n


# ---- Source 6: Concept-name pairs (Procedure) -------------------------


async def emit_procedure_pairs(db: AsyncSession, out, max_n: int | None) -> int:
    rows = (await db.execute(select(Procedure))).scalars().all()
    n = 0
    for p in rows:
        if max_n and n >= max_n:
            break
        if p.english and p.name_iast:
            n += _emit(out, p.english, p.name_iast,
                       "procedure-en-iast", "en", "sa-iast")
        if p.hindi and p.name_iast:
            n += _emit(out, p.hindi, p.name_iast,
                       "procedure-hi-iast", "hi", "sa-iast")
        if p.primary_indication and p.name_iast:
            n += _emit(out, p.primary_indication, p.name_iast,
                       "primary-ind-procedure", "en", "sa-iast")
    return n


# ---- Source 7: Diagnostic-pattern context pairs -----------------------


async def emit_pattern_pairs(db: AsyncSession, out, max_n: int | None) -> int:
    rows = (await db.execute(select(DiagnosticPattern))).scalars().all()
    n = 0
    for pat in rows:
        if max_n and n >= max_n:
            break
        if not pat.description or not pat.targets:
            continue
        for t in pat.targets:
            if max_n and n >= max_n:
                break
            tname = t.get("name") if isinstance(t, dict) else None
            if not tname:
                continue
            n += _emit(out, pat.description, tname,
                       "pattern-target", "en", "sa-iast")
    return n


# ---- Driver -----------------------------------------------------------


async def main(args) -> None:
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    counts: Counter[str] = Counter()
    sources = [
        ("cross-script-verse", emit_cross_script_pairs),
        ("verse-context", emit_verse_context_pairs),
        ("dravya", emit_dravya_pairs),
        ("formulation", emit_formulation_pairs),
        ("vyadhi", emit_vyadhi_pairs),
        ("procedure", emit_procedure_pairs),
        ("pattern", emit_pattern_pairs),
    ]

    print(f"Building training pairs → {out_path}")
    print(f"  max_per_source: {args.max_per_source}")

    with open(out_path, "w", encoding="utf-8") as out:
        async with AsyncSessionLocal() as db:
            for label, fn in sources:
                n = await fn(db, out, args.max_per_source)
                counts[label] = n
                print(f"  {label:24} {n:>6}")

    total = sum(counts.values())
    print(f"\n  TOTAL                    {total:>6} pairs")
    print(f"  Output: {out_path}")
    print(f"\nNext step: review the pairs file, then train via:")
    print("  python -m scripts.finetune_bge --pairs " + str(out_path))


def _parse_args(argv: list[str] | None = None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", default=str(DEFAULT_OUTPUT),
                   help=f"JSONL output path (default {DEFAULT_OUTPUT})")
    p.add_argument("--max-per-source", type=int, default=None,
                   help="Cap pairs per source for fast iteration / debug")
    return p.parse_args(argv)


if __name__ == "__main__":
    asyncio.run(main(_parse_args(sys.argv[1:])))
