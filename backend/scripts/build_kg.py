"""Derive the knowledge_edges table from all source models.

Walks every cross-reference in:
  - Formulation.ingredients   →  Dravya  (ingredient_of, FK-resolved)
  - Vyadhi.common_dravyas     →  Dravya  (indicated_for, name-resolved)
  - Vyadhi.common_formulations → Formulation (indicated_for)
  - Procedure.indications     →  Vyadhi  (indicated_for, name-resolved)
  - Procedure.common_dravyas  →  Dravya  (uses)
  - Procedure.common_oils     →  Formulation (uses, name-resolved)
  - DiagnosticPattern.targets →  Vyadhi  (diagnoses, name-resolved)
  - DiagnosticPattern.suggested_chikitsa → Procedure | Formulation | Dravya
                                          (suggests_chikitsa, multi-kind)
  - DiagnosticPattern.conditions → ParikshaParam (used_in)
  - ModernEvidence            ←  Dravya  (has_evidence, FK)

Strategy:
  1. Wipe existing edges (full rebuild — fast, deterministic, simple).
  2. Build per-kind name→entity resolver indices.
  3. Walk each source model and emit edges.
  4. Bulk-insert.

Re-runnable. After any seed-data change, run this to refresh the KG.

Usage:
    python -m scripts.build_kg
    python -m scripts.build_kg --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Iterable

from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, Base, engine
from app.models import (
    Dravya, Formulation, FormulationIngredient, Vyadhi, Procedure,
    ParikshaParam, DiagnosticPattern, ModernEvidence, KnowledgeEdge,
)
from app.services.kg import get_kg_resolvers, resolve_name


def _edge(
    predicate: str,
    src_kind: str, src_row, src_name: str,
    tgt_kind: str, tgt_row, tgt_name: str,
    confidence: float = 1.0,
    weight: float | None = None,
    provenance: dict | None = None,
) -> KnowledgeEdge:
    return KnowledgeEdge(
        predicate=predicate,
        source_kind=src_kind,
        source_id=getattr(src_row, "id", None) if src_row else None,
        source_name=src_name,
        target_kind=tgt_kind,
        target_id=getattr(tgt_row, "id", None) if tgt_row else None,
        target_name=tgt_name,
        confidence=confidence,
        weight=weight,
        provenance=provenance,
    )


# Multiple targets in suggested_chikitsa may be procedures, formulations,
# or single dravyas. Resolve in this order.
_CHIKITSA_KIND_ORDER = ("procedure", "formulation", "dravya")


def _resolve_chikitsa(name: str, resolvers: dict) -> tuple[str, object | None, float]:
    """Try procedure → formulation → dravya; return (kind, entity, confidence)."""
    for kind in _CHIKITSA_KIND_ORDER:
        ent, conf = resolve_name(name, kind, resolvers)
        if ent is not None:
            return kind, ent, conf
    return "unknown", None, 0.5


# ---- per-source extractors ------------------------------------------


async def derive_from_formulations(db: AsyncSession, resolvers: dict) -> list[KnowledgeEdge]:
    """Formulation ↔ Dravya (ingredient_of) — FK-direct via FormulationIngredient.
    Plus Formulation indications → Vyādhi (indicated_for, name-resolved)."""
    edges: list[KnowledgeEdge] = []
    forms = list((await db.execute(select(Formulation))).scalars().all())
    ings = list(
        (await db.execute(select(FormulationIngredient))).scalars().all()
    )
    form_by_id = {f.id: f for f in forms}
    drav_by_id = {d.id: d for d in (await db.execute(select(Dravya))).scalars().all()}

    for ing in ings:
        form = form_by_id.get(ing.formulation_id)
        if not form:
            continue
        if ing.dravya_id and ing.dravya_id in drav_by_id:
            d = drav_by_id[ing.dravya_id]
            edges.append(_edge(
                "ingredient_of",
                "dravya", d, d.nama_sanskrit,
                "formulation", form, form.name_iast,
                confidence=1.0,
                provenance={"model": "FormulationIngredient", "id": str(ing.id)},
            ))
        else:
            # Unresolved name — keep the edge with target_id NULL so the
            # 'gaps to fill' can be surfaced in admin overview.
            edges.append(_edge(
                "ingredient_of",
                "dravya", None, ing.ingredient_name or "(unknown)",
                "formulation", form, form.name_iast,
                confidence=0.5,
                provenance={"model": "FormulationIngredient", "id": str(ing.id), "unresolved": True},
            ))

    # Formulation indications → Vyādhi
    for f in forms:
        for ind in (f.indications or []):
            if not ind:
                continue
            ent, conf = resolve_name(ind, "vyadhi", resolvers)
            edges.append(_edge(
                "indicated_for",
                "formulation", f, f.name_iast,
                "vyadhi", ent, getattr(ent, "nama_sanskrit", None) or ind,
                confidence=conf,
                provenance={"model": "Formulation", "field": "indications"},
            ))
    return edges


async def derive_from_vyadhi(db: AsyncSession, resolvers: dict) -> list[KnowledgeEdge]:
    edges: list[KnowledgeEdge] = []
    rows = list((await db.execute(select(Vyadhi))).scalars().all())
    for v in rows:
        for d_name in (v.common_dravyas or []):
            if not d_name:
                continue
            ent, conf = resolve_name(d_name, "dravya", resolvers)
            edges.append(_edge(
                "indicated_for",
                "dravya", ent, getattr(ent, "nama_sanskrit", None) or d_name,
                "vyadhi", v, v.nama_sanskrit,
                confidence=conf,
                provenance={"model": "Vyadhi", "field": "common_dravyas"},
            ))
        for f_name in (v.common_formulations or []):
            if not f_name:
                continue
            ent, conf = resolve_name(f_name, "formulation", resolvers)
            edges.append(_edge(
                "indicated_for",
                "formulation", ent, getattr(ent, "name_iast", None) or f_name,
                "vyadhi", v, v.nama_sanskrit,
                confidence=conf,
                provenance={"model": "Vyadhi", "field": "common_formulations"},
            ))
    return edges


async def derive_from_procedures(db: AsyncSession, resolvers: dict) -> list[KnowledgeEdge]:
    edges: list[KnowledgeEdge] = []
    rows = list((await db.execute(select(Procedure))).scalars().all())
    for p in rows:
        for ind in (p.indications or []):
            if not ind:
                continue
            ent, conf = resolve_name(ind, "vyadhi", resolvers)
            edges.append(_edge(
                "indicated_for",
                "procedure", p, p.name_iast,
                "vyadhi", ent, getattr(ent, "nama_sanskrit", None) or ind,
                confidence=conf,
                provenance={"model": "Procedure", "field": "indications"},
            ))
        for d_name in (p.common_dravyas or []):
            if not d_name:
                continue
            ent, conf = resolve_name(d_name, "dravya", resolvers)
            edges.append(_edge(
                "uses",
                "procedure", p, p.name_iast,
                "dravya", ent, getattr(ent, "nama_sanskrit", None) or d_name,
                confidence=conf,
                provenance={"model": "Procedure", "field": "common_dravyas"},
            ))
        for o_name in (p.common_oils or []):
            if not o_name:
                continue
            ent, conf = resolve_name(o_name, "formulation", resolvers)
            edges.append(_edge(
                "uses",
                "procedure", p, p.name_iast,
                "formulation", ent, getattr(ent, "name_iast", None) or o_name,
                confidence=conf,
                provenance={"model": "Procedure", "field": "common_oils"},
            ))
    return edges


async def derive_from_diagnostic_patterns(
    db: AsyncSession, resolvers: dict
) -> list[KnowledgeEdge]:
    edges: list[KnowledgeEdge] = []
    rows = list((await db.execute(select(DiagnosticPattern))).scalars().all())
    for pat in rows:
        # Targets — the diagnoses
        for t in (pat.targets or []):
            tname = t.get("name", "")
            tkind = t.get("target_kind", "vyadhi")
            weight = float(t.get("weight", 1.0))
            if tkind == "vyadhi":
                ent, conf = resolve_name(tname, "vyadhi", resolvers)
                edges.append(_edge(
                    "diagnoses",
                    "diagnostic_pattern", pat, pat.name,
                    "vyadhi", ent, getattr(ent, "nama_sanskrit", None) or tname,
                    confidence=conf,
                    weight=weight,
                    provenance={"model": "DiagnosticPattern", "field": "targets"},
                ))
            else:
                # dosha-state / agni-state / etc. — no entity table; record name-only.
                edges.append(_edge(
                    "diagnoses",
                    "diagnostic_pattern", pat, pat.name,
                    tkind, None, tname,
                    confidence=1.0,
                    weight=weight,
                    provenance={"model": "DiagnosticPattern", "field": "targets"},
                ))

        # Suggested chikitsa — try procedure / formulation / dravya in order.
        for c_name in (pat.suggested_chikitsa or []):
            if not c_name:
                continue
            kind, ent, conf = _resolve_chikitsa(c_name, resolvers)
            edges.append(_edge(
                "suggests_chikitsa",
                "diagnostic_pattern", pat, pat.name,
                kind, ent, getattr(ent, "name_iast", getattr(ent, "nama_sanskrit", None)) or c_name,
                confidence=conf,
                provenance={"model": "DiagnosticPattern", "field": "suggested_chikitsa"},
            ))

        # Conditions — pariksha params used.
        seen_params: set[str] = set()
        for c in (pat.conditions or []):
            pname = c.get("param", "")
            if not pname or pname in seen_params:
                continue
            seen_params.add(pname)
            ent, conf = resolve_name(pname, "pariksha_param", resolvers)
            edges.append(_edge(
                "used_in",
                "pariksha_param", ent, getattr(ent, "name_iast", None) or pname,
                "diagnostic_pattern", pat, pat.name,
                confidence=conf,
                provenance={"model": "DiagnosticPattern", "field": "conditions"},
            ))
    return edges


async def derive_from_modern_evidence(db: AsyncSession) -> list[KnowledgeEdge]:
    edges: list[KnowledgeEdge] = []
    rows = list((await db.execute(select(ModernEvidence))).scalars().all())
    drav_by_id = {
        d.id: d for d in (await db.execute(select(Dravya))).scalars().all()
    }
    for e in rows:
        d = drav_by_id.get(e.dravya_id)
        if not d:
            continue
        edges.append(_edge(
            "has_evidence",
            "dravya", d, d.nama_sanskrit,
            "modern_evidence", e, e.title[:200] if e.title else f"PMID:{e.pmid}",
            confidence=1.0,
            provenance={"model": "ModernEvidence", "pmid": e.pmid},
        ))
    return edges


# ---- driver ----------------------------------------------------------


def _dedupe_edges(edges: Iterable[KnowledgeEdge]) -> list[KnowledgeEdge]:
    """Same signature should not appear twice in one rebuild."""
    seen = set()
    out: list[KnowledgeEdge] = []
    for e in edges:
        sig = (
            e.predicate,
            e.source_kind, str(e.source_id) if e.source_id else None, e.source_name,
            e.target_kind, str(e.target_id) if e.target_id else None, e.target_name,
        )
        if sig in seen:
            continue
        seen.add(sig)
        out.append(e)
    return out


async def main(args) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        resolvers = await get_kg_resolvers(db)
        print(
            f"Resolvers built — "
            f"dravya={len(resolvers['dravya'])} keys, "
            f"formulation={len(resolvers['formulation'])}, "
            f"vyadhi={len(resolvers['vyadhi'])}, "
            f"procedure={len(resolvers['procedure'])}, "
            f"pariksha_param={len(resolvers['pariksha_param'])}, "
            f"diagnostic_pattern={len(resolvers['diagnostic_pattern'])}"
        )

        all_edges: list[KnowledgeEdge] = []
        all_edges.extend(await derive_from_formulations(db, resolvers))
        all_edges.extend(await derive_from_vyadhi(db, resolvers))
        all_edges.extend(await derive_from_procedures(db, resolvers))
        all_edges.extend(await derive_from_diagnostic_patterns(db, resolvers))
        all_edges.extend(await derive_from_modern_evidence(db))
        all_edges = _dedupe_edges(all_edges)

    # Per-predicate summary
    by_pred: dict[str, int] = {}
    by_pred_resolved: dict[str, int] = {}
    for e in all_edges:
        by_pred[e.predicate] = by_pred.get(e.predicate, 0) + 1
        if e.target_id is not None:
            by_pred_resolved[e.predicate] = by_pred_resolved.get(e.predicate, 0) + 1

    print(f"\nDerived {len(all_edges)} edges")
    for pred, n in sorted(by_pred.items(), key=lambda kv: -kv[1]):
        r = by_pred_resolved.get(pred, 0)
        print(f"  {pred:<22} {n:>5} edges   ({r} resolved to UUIDs, {n-r} name-only)")

    if args.dry_run:
        print("\n(dry-run — no writes)")
        return

    async with AsyncSessionLocal() as db:
        await db.execute(delete(KnowledgeEdge))
        await db.commit()
        for e in all_edges:
            db.add(e)
        await db.commit()
        n_total = (await db.execute(select(func.count(KnowledgeEdge.id)))).scalar_one()
    print(f"\nWrote {n_total} edges to knowledge_edges.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                   help="Compute and report counts but don't write to DB")
    asyncio.run(main(p.parse_args(sys.argv[1:])))
