"""Formulation YAML → formulations + formulation_ingredients tables.

Idempotent: upserts by name_iast + kalpana_type. Each formulation's
ingredient list is fully replaced on re-run.

Resolves ingredient_name → dravya_id via case/diacritic-flexible lookup
on Dravya.nama_sanskrit. Where the ingredient doesn't match a known
dravya (compound names like "Triphalā" or rare ingredients), dravya_id
stays null but the ingredient row is preserved.

Usage:
    python -m scripts.ingest_formulations
    python -m scripts.ingest_formulations seed_classical.yaml
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from vidyut.lipi import Scheme, transliterate

from app.database import AsyncSessionLocal, Base, engine
from app.models import Dravya, Formulation, FormulationIngredient  # noqa: F401


DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "formulations"


def _to_devanagari(iast: str | None) -> str | None:
    if not iast:
        return None
    try:
        return transliterate(iast.lower(), Scheme.Iast, Scheme.Devanagari)
    except Exception:
        return None


def _norm_dravya_lookup(s: str) -> str:
    """Lower-case + strip whitespace for fuzzy ingredient↔dravya matching."""
    return (s or "").lower().strip()


_DRAVYA_INDEX_CACHE: dict | None = None


async def _build_dravya_index(db: AsyncSession) -> dict[str, str]:
    """Lazy-build a normalized-name → dravya_id index.

    Diacritic-aware: 'Vāsā' and 'Vāsaka' both index as 'vasaka' / 'vasa'
    so spelling-variants resolve to the same row. Indexes nama_sanskrit,
    english, hindi, and latin_binomial. Caches per-process.
    """
    global _DRAVYA_INDEX_CACHE
    if _DRAVYA_INDEX_CACHE is not None:
        return _DRAVYA_INDEX_CACHE
    from app.services.kg import normalize_name, split_alternatives

    rows = (await db.execute(
        select(Dravya.id, Dravya.nama_sanskrit, Dravya.english,
               Dravya.hindi, Dravya.latin_binomial)
    )).all()
    idx: dict[str, str] = {}
    for r in rows:
        for v in (r.nama_sanskrit, r.english, r.hindi, r.latin_binomial):
            if not v:
                continue
            for variant in [v] + split_alternatives(v):
                key = normalize_name(variant)
                if key:
                    idx.setdefault(key, str(r.id))
    _DRAVYA_INDEX_CACHE = idx
    return idx


# Common Sanskrit anatomical-part suffixes that are often appended to a
# dravya name to specify the part used. We strip these for fallback match.
_PART_SUFFIXES = (
    "-tvak", "-mūla", "-puṣpa", "-patrā", "-patra", "-bīja", "-phala",
    "-majjā", "-sāra", "-kanda", "-kvātha", "-cūrṇa", "-curṇa",
    "-svarasa", "-arka", "-ghṛta", "-taila", "-bhasma", "-piṣṭi",
)


async def _resolve_dravya(db: AsyncSession, ingredient_name: str) -> str | None:
    """Resolve an ingredient name to a Dravya UUID using diacritic-aware
    normalized matching. Tries direct → suffix-stripped → first-token →
    substring fallback.
    """
    from app.services.kg import normalize_name

    if not ingredient_name:
        return None
    head = ingredient_name.split("(")[0].strip()
    head = head.split(",")[0].strip()
    if not head:
        return None

    idx = await _build_dravya_index(db)

    # 1. Direct normalized match
    key = normalize_name(head)
    if key in idx:
        return idx[key]

    # 2. Strip common part-suffixes (e.g. 'Arjuna-tvak' → 'Arjuna')
    for suf in _PART_SUFFIXES:
        if head.endswith(suf):
            stripped = head[:-len(suf)].strip()
            sk = normalize_name(stripped)
            if sk and sk in idx:
                return idx[sk]

    # 3. First-token / first-two-tokens fallback
    tokens = key.split()
    if len(tokens) >= 2:
        if " ".join(tokens[:2]) in idx:
            return idx[" ".join(tokens[:2])]
    if tokens and tokens[0] in idx:
        return idx[tokens[0]]

    # 4. SQL substring fallback (for partial names)
    pattern = f"%{head}%"
    result = await db.execute(
        select(Dravya.id).where(
            (Dravya.nama_sanskrit.ilike(pattern))
            | (Dravya.english.ilike(pattern))
            | (Dravya.latin_binomial.ilike(pattern))
        ).limit(1)
    )
    return result.scalar_one_or_none()


def _provenance(source_file: str) -> dict:
    return {
        "source_file": source_file,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "tool": "Claude Opus 4.7 LLM-curated; classical refs in classical_source",
    }


async def _upsert_formulation(
    db: AsyncSession, row: dict, source_file: str
) -> tuple[str, Formulation]:
    name = (row.get("name_iast") or "").strip()
    kalpana = (row.get("kalpana_type") or "").strip()
    if not name or not kalpana:
        return "skipped", None  # type: ignore[return-value]

    # Match on name_iast alone — kalpana_type can be re-classified during
    # curation (e.g. a Guggulu yoga initially mistagged as 'vaṭī'). Matching
    # on name + kalpana would create duplicate rows on every reclass.
    existing = (await db.execute(
        select(Formulation).where(Formulation.name_iast == name)
    )).scalar_one_or_none()

    payload = {
        "name_iast": name,
        "name_devanagari": row.get("name_devanagari") or _to_devanagari(name),
        "english": row.get("english"),
        "hindi": row.get("hindi"),
        "kalpana_type": kalpana,
        "primary_indication": row.get("primary_indication"),
        "indications": row.get("indications"),
        "dosha_action": row.get("dosha_action"),
        "karma": row.get("karma"),
        "dose_value": row.get("dose_value"),
        "dose_unit": row.get("dose_unit"),
        "anupana": row.get("anupana"),
        "kala": row.get("kala"),
        "duration": row.get("duration"),
        "contraindications": row.get("contraindications"),
        "drug_interactions": row.get("drug_interactions"),
        "pregnancy_lactation_status": row.get("pregnancy_lactation_status"),
        "pediatric_status": row.get("pediatric_status"),
        "toxicity_notes": row.get("toxicity_notes"),
        "afi_ref": row.get("afi_ref"),
        "api_ref": row.get("api_ref"),
        "ayush_stg_url": row.get("ayush_stg_url"),
        "shelf_life_days": row.get("shelf_life_days"),
        "method_summary": row.get("method_summary"),
        "classical_source": row.get("classical_source"),
        "classical_chapter": row.get("classical_chapter"),
        "classical_verse": row.get("classical_verse"),
        "notes": row.get("notes"),
        "review_tier": row.get("review_tier") or "llm-only",
        "provenance": row.get("provenance") or _provenance(source_file),
    }

    if existing:
        for k, v in payload.items():
            setattr(existing, k, v)
        # Drop existing ingredients — full replacement on re-ingest
        await db.execute(
            delete(FormulationIngredient).where(
                FormulationIngredient.formulation_id == existing.id
            )
        )
        await db.flush()
        return "updated", existing

    new = Formulation(**payload)
    db.add(new)
    await db.flush()
    return "inserted", new


async def _add_ingredients(
    db: AsyncSession, formulation: Formulation, ingredients: list[dict]
) -> int:
    if not ingredients:
        return 0
    for i, ing in enumerate(ingredients):
        ing_name = (ing.get("ingredient_name") or "").strip()
        if not ing_name:
            continue
        dravya_id = await _resolve_dravya(db, ing_name)
        db.add(
            FormulationIngredient(
                formulation_id=formulation.id,
                dravya_id=dravya_id,
                ingredient_name=ing_name,
                proportion=ing.get("proportion"),
                role=ing.get("role"),
                processing=ing.get("processing"),
                position=i,
            )
        )
    await db.flush()
    return len([i for i in ingredients if i.get("ingredient_name")])


async def ingest_file(path: Path) -> dict:
    print(f"\nLoading {path}")
    with open(path) as f:
        doc = yaml.safe_load(f)
    rows = doc.get("formulations", [])
    print(f"  {len(rows)} formulations")

    counters = {"inserted": 0, "updated": 0, "skipped": 0, "ingredients": 0, "resolved_dravyas": 0}
    async with AsyncSessionLocal() as db:
        for row in rows:
            outcome, formulation = await _upsert_formulation(db, row, source_file=path.name)
            if outcome == "skipped":
                counters["skipped"] += 1
                continue
            counters[outcome] += 1
            ing_count = await _add_ingredients(db, formulation, row.get("ingredients") or [])
            counters["ingredients"] += ing_count
            # Count how many got resolved to a dravya
            resolved = (await db.execute(
                select(func.count(FormulationIngredient.id))
                .where(
                    FormulationIngredient.formulation_id == formulation.id,
                    FormulationIngredient.dravya_id.is_not(None),
                )
            )).scalar_one()
            counters["resolved_dravyas"] += resolved
        await db.commit()

    print(
        f"  inserted={counters['inserted']} updated={counters['updated']} "
        f"skipped={counters['skipped']}  ingredients={counters['ingredients']} "
        f"(resolved={counters['resolved_dravyas']})"
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

    total = {"inserted": 0, "updated": 0, "ingredients": 0, "resolved_dravyas": 0}
    for p in paths:
        c = await ingest_file(p)
        for k in total:
            total[k] += c.get(k, 0)

    async with AsyncSessionLocal() as db:
        n = (await db.execute(select(func.count(Formulation.id)))).scalar_one()
    print(
        f"\nDone. inserted={total['inserted']} updated={total['updated']}; "
        f"corpus now has {n} formulations, {total['ingredients']} ingredient rows "
        f"({total['resolved_dravyas']} resolved to dravyas)"
    )


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
