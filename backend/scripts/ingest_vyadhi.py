"""Vyādhi YAML → vyadhi table ingestion.

Idempotent: upserts by nama_sanskrit. Devanagari auto-generated from
IAST via vidyut. NAMASTE / ICD-11 codes preserved as-is.

Usage:
    python -m scripts.ingest_vyadhi
    python -m scripts.ingest_vyadhi seed_top30.yaml
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
from app.models import Vyadhi  # noqa: F401


DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "vyadhi"


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
        "tool": "Claude Opus 4.7 LLM-curated; classical refs in classical_refs",
    }


async def _upsert_vyadhi(db: AsyncSession, row: dict, source_file: str) -> str:
    name = (row.get("nama_sanskrit") or "").strip()
    if not name:
        return "skipped"

    existing = (await db.execute(
        select(Vyadhi).where(Vyadhi.nama_sanskrit == name)
    )).scalar_one_or_none()

    payload = {
        "nama_sanskrit": name,
        "nama_devanagari": row.get("nama_devanagari") or _to_devanagari(name),
        "english": row.get("english"),
        "hindi": row.get("hindi"),
        "synonyms": row.get("synonyms"),
        "namaste_code": row.get("namaste_code"),
        "icd11_tm2_code": row.get("icd11_tm2_code"),
        "icd11_main_code": row.get("icd11_main_code"),
        "chapter": row.get("chapter"),
        "dosha_typology": row.get("dosha_typology"),
        "primary_dosha": row.get("primary_dosha"),
        "primary_dushya": row.get("primary_dushya"),
        "srotas": row.get("srotas"),
        "nidana": row.get("nidana"),
        "purva_rupa": row.get("purva_rupa"),
        "rupa": row.get("rupa"),
        "upashaya": row.get("upashaya"),
        "samprapti_summary": row.get("samprapti_summary"),
        "sadhya_asadhya": row.get("sadhya_asadhya"),
        "chikitsa_summary": row.get("chikitsa_summary"),
        "common_formulations": row.get("common_formulations"),
        "common_dravyas": row.get("common_dravyas"),
        "modern_diagnostics": row.get("modern_diagnostics"),
        "red_flags_for_referral": row.get("red_flags_for_referral"),
        "classical_refs": row.get("classical_refs"),
        "ayush_stg_url": row.get("ayush_stg_url"),
        "notes": row.get("notes"),
        "review_tier": row.get("review_tier") or "llm-only",
        "provenance": row.get("provenance") or _provenance(source_file),
    }

    if existing:
        for k, v in payload.items():
            setattr(existing, k, v)
        return "updated"

    db.add(Vyadhi(**payload))
    return "inserted"


async def ingest_file(path: Path) -> dict:
    print(f"\nLoading {path}")
    with open(path) as f:
        doc = yaml.safe_load(f)
    rows = doc.get("vyadhi", [])
    print(f"  {len(rows)} vyādhi rows")

    counters = {"inserted": 0, "updated": 0, "skipped": 0}
    async with AsyncSessionLocal() as db:
        for row in rows:
            counters[await _upsert_vyadhi(db, row, source_file=path.name)] += 1
        await db.commit()

    print(f"  inserted={counters['inserted']} updated={counters['updated']} skipped={counters['skipped']}")
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

    total = {"inserted": 0, "updated": 0}
    for p in paths:
        c = await ingest_file(p)
        for k in total:
            total[k] += c[k]

    async with AsyncSessionLocal() as db:
        n = (await db.execute(select(func.count(Vyadhi.id)))).scalar_one()
    print(f"\nDone. inserted={total['inserted']} updated={total['updated']}; corpus now has {n} vyādhi entries")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
