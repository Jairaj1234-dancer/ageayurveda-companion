"""Procedure YAML → procedures table ingestion.

Idempotent: upserts by name_iast. Devanagari auto-generated from IAST
via vidyut when not supplied.

Usage:
    python -m scripts.ingest_procedures
    python -m scripts.ingest_procedures seed_top30.yaml
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from vidyut.lipi import Scheme, transliterate

from app.database import AsyncSessionLocal, Base, engine
from app.models import Procedure  # noqa: F401


DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "procedures"


def _to_devanagari(iast: str | None) -> str | None:
    if not iast:
        return None
    try:
        return transliterate(iast.lower(), Scheme.Iast, Scheme.Devanagari)
    except Exception:
        return None


def _provenance(source_file: str) -> dict:
    return {
        "source_file": source_file,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "tool": "Claude Opus 4.7 LLM-curated; classical refs in classical_source/classical_refs",
    }


async def _upsert_procedure(db: AsyncSession, row: dict, source_file: str) -> str:
    name = (row.get("name_iast") or "").strip()
    if not name:
        return "skipped"
    if not row.get("category"):
        # category is required by the schema; refuse silent insert without one
        return "skipped"

    existing = (await db.execute(
        select(Procedure).where(Procedure.name_iast == name)
    )).scalar_one_or_none()

    payload = {
        "name_iast": name,
        "name_devanagari": row.get("name_devanagari") or _to_devanagari(name),
        "english": row.get("english"),
        "hindi": row.get("hindi"),
        "synonyms": row.get("synonyms"),
        "category": row.get("category"),
        "subcategory": row.get("subcategory"),
        "practitioner_level": row.get("practitioner_level") or "vaidya-only",
        "primary_indication": row.get("primary_indication"),
        "indications": row.get("indications"),
        "dosha_action": row.get("dosha_action"),
        "contraindications": row.get("contraindications"),
        "purva_karma": row.get("purva_karma"),
        "pradhana_karma": row.get("pradhana_karma"),
        "paschat_karma": row.get("paschat_karma"),
        "materials": row.get("materials"),
        "common_oils": row.get("common_oils"),
        "common_dravyas": row.get("common_dravyas"),
        "duration_days": row.get("duration_days"),
        "duration_notes": row.get("duration_notes"),
        "frequency": row.get("frequency"),
        "season": row.get("season"),
        "time_of_day": row.get("time_of_day"),
        "adverse_events": row.get("adverse_events"),
        "pregnancy_lactation_status": row.get("pregnancy_lactation_status"),
        "pediatric_status": row.get("pediatric_status"),
        "geriatric_status": row.get("geriatric_status"),
        "red_flags": row.get("red_flags"),
        "modern_correlate": row.get("modern_correlate"),
        "spa_friendly_version": row.get("spa_friendly_version"),
        "classical_source": row.get("classical_source"),
        "classical_refs": row.get("classical_refs"),
        "afi_ref": row.get("afi_ref"),
        "ayush_stg_url": row.get("ayush_stg_url"),
        "description": row.get("description"),
        "notes": row.get("notes"),
        "review_tier": row.get("review_tier") or "llm-only",
        "provenance": row.get("provenance") or _provenance(source_file),
    }

    if existing:
        for k, v in payload.items():
            setattr(existing, k, v)
        return "updated"

    db.add(Procedure(**payload))
    return "inserted"


async def ingest_file(path: Path) -> dict:
    print(f"\nLoading {path}")
    with open(path) as f:
        doc = yaml.safe_load(f)
    rows = doc.get("procedures", [])
    print(f"  {len(rows)} procedure rows")

    counters = {"inserted": 0, "updated": 0, "skipped": 0}
    async with AsyncSessionLocal() as db:
        for row in rows:
            counters[await _upsert_procedure(db, row, source_file=path.name)] += 1
        await db.commit()

    print(f"  inserted={counters['inserted']} updated={counters['updated']} "
          f"skipped={counters['skipped']}")
    return counters


async def main(targets: list[str]) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if not targets:
        paths = sorted(DATA_DIR.glob("*.yaml"))
    else:
        paths = []
        for t in targets:
            p = Path(t)
            if not p.exists():
                p = DATA_DIR / t
            if p.exists():
                paths.append(p)
            else:
                print(f"  not found: {t}")

    if not paths:
        print("No YAML files to ingest.")
        return

    total = {"inserted": 0, "updated": 0, "skipped": 0}
    for p in paths:
        c = await ingest_file(p)
        for k in total:
            total[k] += c[k]

    async with AsyncSessionLocal() as db:
        n = (await db.execute(select(func.count(Procedure.id)))).scalar_one()
        by_cat = (await db.execute(
            select(Procedure.category, func.count(Procedure.id))
            .group_by(Procedure.category)
        )).all()
    print(
        f"\nDone. inserted={total['inserted']} updated={total['updated']} "
        f"skipped={total['skipped']}; corpus now has {n} procedures"
    )
    for cat, cnt in by_cat:
        print(f"  {cat:<16} {cnt}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
