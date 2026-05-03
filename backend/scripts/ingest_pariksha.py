"""Parīkṣā YAML → pariksha_params + diagnostic_patterns ingestion.

Ingests two YAMLs:
  - seed_params.yaml      → ParikshaParam rows (canonical examination
                            parameters with finding picklists).
  - seed_patterns.yaml    → DiagnosticPattern rows (rules linking
                            findings to vyādhi/doṣa/agni candidates).

Idempotent: param upsert by name_iast; pattern upsert by name.

Usage:
    python -m scripts.ingest_pariksha
    python -m scripts.ingest_pariksha seed_params.yaml
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
from app.models import ParikshaParam, DiagnosticPattern  # noqa: F401


DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "pariksha"


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
        "tool": "Claude Opus 4.7 LLM-curated; classical refs in classical_source",
    }


# ---- params -----------------------------------------------------------


async def _upsert_param(db: AsyncSession, row: dict, source_file: str) -> str:
    name = (row.get("name_iast") or "").strip()
    if not name or not row.get("schema_family"):
        return "skipped"

    existing = (await db.execute(
        select(ParikshaParam).where(ParikshaParam.name_iast == name)
    )).scalar_one_or_none()

    payload = {
        "name_iast": name,
        "name_devanagari": row.get("name_devanagari") or _to_devanagari(name),
        "english": row.get("english"),
        "hindi": row.get("hindi"),
        "schema_family": row.get("schema_family"),
        "domain": row.get("domain"),
        "examination_method": row.get("examination_method"),
        "when_to_examine": row.get("when_to_examine"),
        "findings": row.get("findings"),
        "normal_finding": row.get("normal_finding"),
        "classical_source": row.get("classical_source"),
        "classical_refs": row.get("classical_refs"),
        "notes": row.get("notes"),
        "review_tier": row.get("review_tier") or "llm-only",
        "provenance": row.get("provenance") or _provenance(source_file),
    }

    if existing:
        for k, v in payload.items():
            setattr(existing, k, v)
        return "updated"

    db.add(ParikshaParam(**payload))
    return "inserted"


# ---- patterns ---------------------------------------------------------


async def _upsert_pattern(db: AsyncSession, row: dict, source_file: str) -> str:
    name = (row.get("name") or "").strip()
    if not name or not row.get("conditions") or not row.get("targets"):
        return "skipped"

    existing = (await db.execute(
        select(DiagnosticPattern).where(DiagnosticPattern.name == name)
    )).scalar_one_or_none()

    payload = {
        "name": name,
        "description": row.get("description"),
        "pattern_type": row.get("pattern_type") or "vyadhi",
        "conditions": row.get("conditions"),
        "targets": row.get("targets"),
        "suggested_chikitsa": row.get("suggested_chikitsa"),
        "red_flags": row.get("red_flags"),
        "evidence_grade": row.get("evidence_grade") or "C",
        "classical_source": row.get("classical_source"),
        "classical_refs": row.get("classical_refs"),
        "notes": row.get("notes"),
        "review_tier": row.get("review_tier") or "llm-only",
        "provenance": row.get("provenance") or _provenance(source_file),
    }

    if existing:
        for k, v in payload.items():
            setattr(existing, k, v)
        return "updated"

    db.add(DiagnosticPattern(**payload))
    return "inserted"


# ---- driver -----------------------------------------------------------


async def ingest_file(path: Path) -> dict:
    print(f"\nLoading {path}")
    with open(path) as f:
        doc = yaml.safe_load(f)

    counters = {"inserted": 0, "updated": 0, "skipped": 0}

    if "pariksha_params" in doc:
        rows = doc["pariksha_params"]
        print(f"  {len(rows)} parīkṣā parameter rows")
        async with AsyncSessionLocal() as db:
            for row in rows:
                counters[await _upsert_param(db, row, source_file=path.name)] += 1
            await db.commit()
    elif "diagnostic_patterns" in doc:
        rows = doc["diagnostic_patterns"]
        print(f"  {len(rows)} diagnostic-pattern rows")
        async with AsyncSessionLocal() as db:
            for row in rows:
                counters[await _upsert_pattern(db, row, source_file=path.name)] += 1
            await db.commit()
    else:
        print("  unknown YAML structure (expected 'pariksha_params' or 'diagnostic_patterns')")
        return counters

    print(
        f"  inserted={counters['inserted']} updated={counters['updated']} "
        f"skipped={counters['skipped']}"
    )
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
        n_params = (await db.execute(select(func.count(ParikshaParam.id)))).scalar_one()
        n_patterns = (await db.execute(select(func.count(DiagnosticPattern.id)))).scalar_one()
    print(
        f"\nDone. inserted={total['inserted']} updated={total['updated']} "
        f"skipped={total['skipped']}"
    )
    print(f"  pariksha_params:     {n_params}")
    print(f"  diagnostic_patterns: {n_patterns}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
