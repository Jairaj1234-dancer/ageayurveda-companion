"""Dravya YAML → dravyas table ingestion.

Reads YAML files under app/data/dravyas/ and loads them into the dravyas
table. Each YAML row is matched by nama_sanskrit + latin_binomial; existing
rows are upserted. Devanagari is generated at ingest time from the IAST
nama_sanskrit via vidyut.lipi.

Re-running is safe — rows are upserted by (nama_sanskrit, latin_binomial).

Usage:
    python -m scripts.ingest_dravyas                 # all .yaml in app/data/dravyas/
    python -m scripts.ingest_dravyas seed_top30.yaml # single file
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from vidyut.lipi import Scheme, transliterate

from app.database import AsyncSessionLocal, Base, engine
from app.models import Dravya  # noqa: F401 — registers all models


DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "dravyas"


def _to_devanagari(iast: str | None) -> str | None:
    """Transliterate IAST → Devanagari. vidyut expects lowercase IAST —
    capital letters are passed through unchanged. We lowercase first
    (Sanskrit has no case anyway) but preserve any non-IAST punctuation."""
    if not iast:
        return None
    try:
        return transliterate(iast.lower(), Scheme.Iast, Scheme.Devanagari)
    except Exception:
        return None


def _row_provenance(source_file: str) -> dict:
    return {
        "source_file": source_file,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "tool": "Claude Opus 4.7 LLM-curated; classical references in nighantu_refs",
    }


async def _upsert_dravya(db: AsyncSession, row: dict, source_file: str) -> str:
    """Returns 'inserted' or 'updated'."""
    name = row.get("nama_sanskrit", "").strip()
    latin = (row.get("latin_binomial") or "").strip() or None
    if not name:
        return "skipped"

    # Match on (nama_sanskrit, latin_binomial) — Latin binomial is the most
    # stable identifier; fall back to Sanskrit name only if Latin is empty.
    stmt = select(Dravya).where(Dravya.nama_sanskrit == name)
    if latin:
        stmt = stmt.where(Dravya.latin_binomial == latin)
    existing = (await db.execute(stmt)).scalar_one_or_none()

    payload = {
        "nama_sanskrit": name,
        "nama_devanagari": row.get("nama_devanagari") or _to_devanagari(name),
        "latin_binomial": latin,
        "family": row.get("family"),
        "english": row.get("english"),
        "hindi": row.get("hindi"),
        "regional_names": row.get("regional_names"),
        "dravya_type": row.get("dravya_type") or "sthāvara",
        "varga_bhavaprakasha": row.get("varga_bhavaprakasha"),
        "varga_other": row.get("varga_other"),
        "part_used": row.get("part_used"),
        "rasa": row.get("rasa"),
        "guna": row.get("guna"),
        "virya": row.get("virya"),
        "vipaka": row.get("vipaka"),
        "prabhava": row.get("prabhava"),
        "dosha_karma": row.get("dosha_karma"),
        "karma": row.get("karma"),
        "prayoga": row.get("prayoga"),
        "matra_value": row.get("matra_value"),
        "matra_unit": row.get("matra_unit"),
        "anupana": row.get("anupana"),
        "kala": row.get("kala"),
        "contraindications": row.get("contraindications"),
        "viruddha": row.get("viruddha"),
        "toxicity_notes": row.get("toxicity_notes"),
        "pregnancy_lactation_status": row.get("pregnancy_lactation_status"),
        "pratinidhi_dravya": row.get("pratinidhi_dravya"),
        "api_monograph_ref": row.get("api_monograph_ref"),
        "nighantu_refs": row.get("nighantu_refs"),
        "imppat_id": row.get("imppat_id"),
        "wikidata_qid": row.get("wikidata_qid"),
        "pubchem_cid": row.get("pubchem_cid"),
        "notes": row.get("notes"),
        "review_tier": row.get("review_tier") or "llm-only",
        "provenance": row.get("provenance") or _row_provenance(source_file),
    }

    if existing:
        for k, v in payload.items():
            setattr(existing, k, v)
        return "updated"

    db.add(Dravya(**payload))
    return "inserted"


async def ingest_file(path: Path) -> dict:
    print(f"\nLoading {path}")
    with open(path) as f:
        doc = yaml.safe_load(f)
    rows = doc.get("dravyas", [])
    print(f"  {len(rows)} rows")

    counters = {"inserted": 0, "updated": 0, "skipped": 0}
    async with AsyncSessionLocal() as db:
        for row in rows:
            outcome = await _upsert_dravya(db, row, source_file=path.name)
            counters[outcome] += 1
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
            if not p.exists():
                print(f"  not found: {t}"); continue
            paths.append(p)

    if not paths:
        print("No YAML files to ingest.")
        return

    total = {"inserted": 0, "updated": 0, "skipped": 0}
    for p in paths:
        c = await ingest_file(p)
        for k, v in c.items():
            total[k] += v

    # Summary
    async with AsyncSessionLocal() as db:
        from sqlalchemy import func as f
        n = (await db.execute(select(f.count(Dravya.id)))).scalar_one()
    print(f"\nDone. inserted={total['inserted']} updated={total['updated']}; corpus now has {n} dravyas")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
