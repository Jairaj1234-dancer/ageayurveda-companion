"""Knowledge-graph query helpers + name-resolution layer.

`resolve_name` performs diacritic-aware fuzzy lookup so a string like
'Aśvagandhā' or 'Ashwagandha' both resolve to the same Dravya row. Used
by the KG builder to set edge.target_id when a cross-ref name matches an
entity row.

`neighbors` and `subgraph` provide cheap KG queries for chatbot grounding.
"""
from __future__ import annotations

import unicodedata
from typing import Iterable

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Dravya,
    Formulation,
    Vyadhi,
    Procedure,
    ParikshaParam,
    DiagnosticPattern,
    ModernEvidence,
    KnowledgeEdge,
)


# ---- name normalization ----------------------------------------------

# IAST diacritic characters that English transliterations spell as digraphs.
_IAST_DIGRAPH_MAP = str.maketrans({
    "ṣ": "sh", "ś": "sh", "ṛ": "ri", "ṝ": "ri",
    "ṭ": "t", "ḍ": "d", "ṇ": "n", "ṅ": "n", "ñ": "n",
    "ṃ": "m", "ḥ": "h",
    "Ṣ": "Sh", "Ś": "Sh", "Ṛ": "Ri",
    "Ṭ": "T", "Ḍ": "D", "Ṇ": "N", "Ṅ": "N", "Ñ": "N",
    "Ṃ": "M", "Ḥ": "H",
})


def normalize_name(s: str | None) -> str:
    """Lowercase + strip diacritics + collapse whitespace.

    Two normalizations applied in order:
      1. Map IAST diacritics to English digraphs (ṣ→sh, ṛ→ri).
      2. NFKD-decompose and drop combining marks (covers ā, ī, ū, etc.).

    The result is what we hash on for fuzzy name matching.
    """
    if not s:
        return ""
    s = s.translate(_IAST_DIGRAPH_MAP)
    decomposed = unicodedata.normalize("NFKD", s)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.lower().split())


def split_alternatives(s: str) -> list[str]:
    """A seed YAML may encode 'Curṇa A / Curṇa B' or 'Foo (form-X)' or
    'Elā (Sūkṣma-elā)'. Yield each form independently for matching:
    bare head, slash-split alternatives, AND paren content (with and
    without internal hyphens)."""
    if not s:
        return []
    head = s.split("(")[0].strip()
    out: list[str] = []

    def _push(c: str) -> None:
        c = c.strip()
        if c and c not in out:
            out.append(c)

    if "/" in head:
        # When the head contains alternatives, push only the split forms,
        # not the combined string (which can't match a single dravya name).
        for p in head.split("/"):
            _push(p)
    else:
        _push(head)

    # Paren content
    if "(" in s and ")" in s:
        try:
            paren = s[s.index("(") + 1:s.rindex(")")].strip()
            if paren:
                _push(paren)
                # Also strip hyphens that act as connectors
                _push(paren.replace("-", " "))
                if "/" in paren:
                    for p in paren.split("/"):
                        _push(p)
        except ValueError:
            pass

    return out


# ---- name → entity resolvers -----------------------------------------


async def _all(db: AsyncSession, model):
    return list((await db.execute(select(model))).scalars().all())


async def _build_index(db: AsyncSession, model, name_attrs: list[str]) -> dict[str, object]:
    """Map normalized name(s) → entity. Each entity is indexed under
    every non-empty attribute in `name_attrs`."""
    rows = await _all(db, model)
    idx: dict[str, object] = {}
    for row in rows:
        for attr in name_attrs:
            v = getattr(row, attr, None)
            if not v:
                continue
            for variant in [v] + split_alternatives(v):
                key = normalize_name(variant)
                if key:
                    idx.setdefault(key, row)
    return idx


async def get_kg_resolvers(db: AsyncSession) -> dict:
    """One-shot fetch of all resolver dicts. Builder calls this once."""
    return {
        "dravya": await _build_index(db, Dravya, ["nama_sanskrit", "english", "hindi"]),
        "formulation": await _build_index(db, Formulation, ["name_iast", "english", "hindi"]),
        "vyadhi": await _build_index(db, Vyadhi, ["nama_sanskrit", "english", "hindi"]),
        "procedure": await _build_index(db, Procedure, ["name_iast", "english", "hindi"]),
        "pariksha_param": await _build_index(db, ParikshaParam, ["name_iast", "english"]),
        "diagnostic_pattern": await _build_index(db, DiagnosticPattern, ["name"]),
    }


def resolve_name(name: str, kind: str, resolvers: dict) -> tuple[object | None, float]:
    """Return (entity_or_None, confidence)."""
    if not name:
        return None, 0.0
    idx = resolvers.get(kind, {})
    key = normalize_name(name)
    direct = idx.get(key)
    if direct is not None:
        return direct, 1.0
    # Trailing-token strip — 'Triphalā Curṇa' → match on 'Triphalā'.
    tokens = key.split()
    if len(tokens) >= 2:
        trimmed = " ".join(tokens[:-1])
        partial = idx.get(trimmed)
        if partial is not None:
            return partial, 0.7
    # First-two-tokens (binomial-style) fallback.
    if len(tokens) >= 2:
        head = " ".join(tokens[:2])
        partial = idx.get(head)
        if partial is not None:
            return partial, 0.7
    return None, 0.5


# ---- query helpers ----------------------------------------------------


async def neighbors(
    db: AsyncSession,
    kind: str,
    entity_id,
    predicate: str | None = None,
    direction: str = "both",
) -> dict[str, list[dict]]:
    """All KG neighbors of an entity, grouped by predicate.

    direction: 'out' (entity is source) | 'in' (entity is target) | 'both'.
    """
    out_clauses = []
    if direction in ("out", "both"):
        out_clauses.append(
            (KnowledgeEdge.source_kind == kind) & (KnowledgeEdge.source_id == entity_id)
        )
    if direction in ("in", "both"):
        out_clauses.append(
            (KnowledgeEdge.target_kind == kind) & (KnowledgeEdge.target_id == entity_id)
        )
    if not out_clauses:
        return {}

    stmt = select(KnowledgeEdge).where(or_(*out_clauses))
    if predicate:
        stmt = stmt.where(KnowledgeEdge.predicate == predicate)
    edges = list((await db.execute(stmt)).scalars().all())

    grouped: dict[str, list[dict]] = {}
    for e in edges:
        is_out = e.source_kind == kind and e.source_id == entity_id
        edge_dict = {
            "predicate": e.predicate,
            "direction": "out" if is_out else "in",
            "other_kind": e.target_kind if is_out else e.source_kind,
            "other_id": str(e.target_id) if (e.target_id and is_out) else
                        (str(e.source_id) if (e.source_id and not is_out) else None),
            "other_name": e.target_name if is_out else e.source_name,
            "confidence": e.confidence,
            "weight": e.weight,
        }
        grouped.setdefault(e.predicate, []).append(edge_dict)
    return grouped


async def subgraph(
    db: AsyncSession,
    kind: str,
    entity_id,
    depth: int = 1,
    predicates: Iterable[str] | None = None,
) -> dict:
    """BFS expansion to `depth` from the seed entity. Returns
    {nodes: [...], edges: [...]} where each node is identified by
    (kind, id_or_name) and edges carry predicate + direction."""
    visited: set[tuple] = set()
    nodes_out: list[dict] = []
    edges_out: list[dict] = []
    frontier: list[tuple] = [(kind, str(entity_id) if entity_id else None, None)]
    visited.add((kind, str(entity_id)))
    nodes_out.append({"kind": kind, "id": str(entity_id), "name": None})

    pred_set = set(predicates) if predicates else None

    for _ in range(depth):
        next_frontier: list[tuple] = []
        for (k, node_id, _) in frontier:
            if not node_id:
                continue
            grouped = await neighbors(db, k, node_id)
            for predicate, edges in grouped.items():
                if pred_set and predicate not in pred_set:
                    continue
                for e in edges:
                    other_key = (e["other_kind"], e["other_id"] or e["other_name"])
                    edges_out.append({
                        "from_kind": k, "from_id": node_id,
                        "to_kind": e["other_kind"], "to_id": e["other_id"],
                        "to_name": e["other_name"],
                        "predicate": predicate,
                        "direction": e["direction"],
                        "confidence": e["confidence"],
                    })
                    if other_key not in visited:
                        visited.add(other_key)
                        nodes_out.append({
                            "kind": e["other_kind"],
                            "id": e["other_id"],
                            "name": e["other_name"],
                        })
                        next_frontier.append((e["other_kind"], e["other_id"], e["other_name"]))
        frontier = next_frontier
        if not frontier:
            break

    return {"nodes": nodes_out, "edges": edges_out}
