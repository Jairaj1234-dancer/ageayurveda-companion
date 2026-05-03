"""Knowledge-graph tests — name normalization, resolution, edge derivation,
neighbors/subgraph queries."""
import pytest
from sqlalchemy import select

from app.models import (
    Dravya, Formulation, FormulationIngredient, Vyadhi, Procedure,
    ParikshaParam, DiagnosticPattern, ModernEvidence, KnowledgeEdge,
)
from app.services import kg as kg_service


# ---- normalization ---------------------------------------------------


def test_normalize_strips_diacritics_and_lowercases():
    assert kg_service.normalize_name("Aśvagandhā") == "ashvagandha"
    assert kg_service.normalize_name("Triphalā Curṇa") == "triphala curna"


def test_normalize_collapses_whitespace():
    assert kg_service.normalize_name("  Foo   bar ") == "foo bar"


def test_normalize_handles_none_and_empty():
    assert kg_service.normalize_name(None) == ""
    assert kg_service.normalize_name("") == ""


def test_split_alternatives_handles_slash_and_parens():
    assert kg_service.split_alternatives("Foo / Bar") == ["Foo", "Bar"]
    # Paren content is now also extracted as an alternative — important for
    # multi-name dravyas like 'Elā (Sūkṣma-elā)' to resolve under both names.
    out = kg_service.split_alternatives("Foo (variant)")
    assert "Foo" in out
    assert "variant" in out
    assert kg_service.split_alternatives("Plain") == ["Plain"]


def test_split_alternatives_extracts_paren_with_hyphens():
    """'Elā (Sūkṣma-elā)' must produce both the bare and dehyphenated forms."""
    out = kg_service.split_alternatives("Elā (Sūkṣma-elā)")
    assert "Elā" in out
    assert "Sūkṣma-elā" in out
    assert "Sūkṣma elā" in out  # hyphen-stripped variant for matching


# ---- resolver --------------------------------------------------------


async def _seed_minimal(db_session):
    """Insert a minimal cross-cutting graph for resolver/builder tests."""
    d_ash = Dravya(nama_sanskrit="Aśvagandhā", latin_binomial="Withania somnifera",
                   english="Winter cherry")
    d_triphala_haritaki = Dravya(nama_sanskrit="Harītakī", latin_binomial="Terminalia chebula")
    f_yogaraja = Formulation(name_iast="Yogarāja Guggulu", english="Yogaraja Guggulu",
                             kalpana_type="guggulu", indications=["Āmavāta", "Sandhivāta"])
    v_amavata = Vyadhi(nama_sanskrit="Āmavāta", english="Amavata",
                       common_dravyas=["Aśvagandhā"], common_formulations=["Yogarāja Guggulu"])
    proc_kati = Procedure(
        name_iast="Kaṭi Basti", english="Lumbar oil pool", category="kriyā-bāhya",
        indications=["Āmavāta"], common_dravyas=["Aśvagandhā"],
        common_oils=["Yogarāja Guggulu"],
    )
    param_nadi = ParikshaParam(
        name_iast="Nāḍī", schema_family="aṣṭa-vidha",
        findings=[{"value": "vāta-nāḍī"}],
    )
    pat = DiagnosticPattern(
        name="Test Āmavāta pattern", pattern_type="vyadhi",
        conditions=[{"param": "Nāḍī", "finding": "vāta-nāḍī", "required": True}],
        targets=[{"target_kind": "vyadhi", "name": "Āmavāta", "weight": 1.0}],
        suggested_chikitsa=["Kaṭi Basti", "Yogarāja Guggulu", "Aśvagandhā"],
    )
    db_session.add_all(
        [d_ash, d_triphala_haritaki, f_yogaraja, v_amavata, proc_kati, param_nadi, pat]
    )
    await db_session.commit()
    # ingredient row needs FK
    db_session.add(FormulationIngredient(
        formulation_id=f_yogaraja.id, dravya_id=d_ash.id,
        ingredient_name="Aśvagandhā", position=1,
    ))
    db_session.add(FormulationIngredient(
        formulation_id=f_yogaraja.id, dravya_id=None,
        ingredient_name="Unmatched-herb", position=2,
    ))
    db_session.add(ModernEvidence(
        pmid="12345", title="Withania somnifera RCT", evidence_tier="B",
        dravya_id=d_ash.id,
    ))
    await db_session.commit()
    return {
        "dravyas": [d_ash, d_triphala_haritaki],
        "formulation": f_yogaraja, "vyadhi": v_amavata,
        "procedure": proc_kati, "param": param_nadi, "pattern": pat,
    }


async def test_resolver_indexes_each_kind(db_session):
    await _seed_minimal(db_session)
    resolvers = await kg_service.get_kg_resolvers(db_session)
    assert "dravya" in resolvers
    assert "formulation" in resolvers
    assert kg_service.normalize_name("Aśvagandhā") in resolvers["dravya"]


async def test_resolve_name_exact_match_is_full_confidence(db_session):
    seeded = await _seed_minimal(db_session)
    resolvers = await kg_service.get_kg_resolvers(db_session)
    ent, conf = kg_service.resolve_name("Aśvagandhā", "dravya", resolvers)
    assert ent is not None
    assert conf == 1.0
    assert ent.id == seeded["dravyas"][0].id


async def test_resolve_name_diacritic_insensitive(db_session):
    """'Ashwagandha' (no diacritics) must resolve to 'Aśvagandhā'."""
    await _seed_minimal(db_session)
    resolvers = await kg_service.get_kg_resolvers(db_session)
    ent, conf = kg_service.resolve_name("Ashvagandha", "dravya", resolvers)
    assert ent is not None
    assert conf == 1.0


async def test_resolve_name_no_match_returns_low_confidence(db_session):
    await _seed_minimal(db_session)
    resolvers = await kg_service.get_kg_resolvers(db_session)
    ent, conf = kg_service.resolve_name("Nonexistent herb", "dravya", resolvers)
    assert ent is None
    assert conf == 0.5


async def test_resolve_name_trailing_token_strip(db_session):
    """'Yogarāja Guggulu Curṇa' → match 'Yogarāja Guggulu'."""
    await _seed_minimal(db_session)
    resolvers = await kg_service.get_kg_resolvers(db_session)
    ent, conf = kg_service.resolve_name("Yogarāja Guggulu Curṇa", "formulation", resolvers)
    assert ent is not None
    assert conf == 0.7


# ---- builder ---------------------------------------------------------


async def test_builder_emits_ingredient_of_edges(db_session):
    """FK-direct edges are emitted at confidence 1.0.
    For ingredient_of (dravya → formulation), the *source_id* is the
    indicator of resolution: a name-only ingredient row has no source_id."""
    seeded = await _seed_minimal(db_session)
    from scripts.build_kg import derive_from_formulations
    resolvers = await kg_service.get_kg_resolvers(db_session)
    edges = await derive_from_formulations(db_session, resolvers)
    ing_edges = [e for e in edges if e.predicate == "ingredient_of"]
    # one resolved + one unresolved ingredient
    assert len(ing_edges) == 2
    resolved = [e for e in ing_edges if e.source_id is not None]
    unresolved = [e for e in ing_edges if e.source_id is None]
    assert len(resolved) == 1
    assert resolved[0].source_name == "Aśvagandhā"
    assert resolved[0].target_name == "Yogarāja Guggulu"
    assert resolved[0].confidence == 1.0
    assert len(unresolved) == 1
    assert unresolved[0].source_name == "Unmatched-herb"
    assert unresolved[0].confidence == 0.5


async def test_builder_emits_indicated_for_from_formulations(db_session):
    await _seed_minimal(db_session)
    from scripts.build_kg import derive_from_formulations
    resolvers = await kg_service.get_kg_resolvers(db_session)
    edges = await derive_from_formulations(db_session, resolvers)
    ind_edges = [e for e in edges if e.predicate == "indicated_for"]
    # Yogarāja Guggulu indicated_for [Āmavāta, Sandhivāta]
    assert len(ind_edges) == 2
    targets = {e.target_name for e in ind_edges}
    assert "Āmavāta" in targets


async def test_builder_emits_diagnoses_and_suggests_chikitsa(db_session):
    await _seed_minimal(db_session)
    from scripts.build_kg import derive_from_diagnostic_patterns
    resolvers = await kg_service.get_kg_resolvers(db_session)
    edges = await derive_from_diagnostic_patterns(db_session, resolvers)

    diag = [e for e in edges if e.predicate == "diagnoses"]
    assert len(diag) == 1
    assert diag[0].target_name == "Āmavāta"

    chikitsa = [e for e in edges if e.predicate == "suggests_chikitsa"]
    assert len(chikitsa) == 3
    kinds = {e.target_kind for e in chikitsa}
    # Should resolve "Kaṭi Basti" → procedure, "Yogarāja Guggulu" → formulation,
    # "Aśvagandhā" → dravya
    assert kinds == {"procedure", "formulation", "dravya"}


async def test_builder_emits_used_in_for_pariksha_params(db_session):
    await _seed_minimal(db_session)
    from scripts.build_kg import derive_from_diagnostic_patterns
    resolvers = await kg_service.get_kg_resolvers(db_session)
    edges = await derive_from_diagnostic_patterns(db_session, resolvers)
    used_in = [e for e in edges if e.predicate == "used_in"]
    assert len(used_in) == 1
    assert used_in[0].source_name == "Nāḍī"
    assert used_in[0].target_name == "Test Āmavāta pattern"


async def test_builder_emits_has_evidence(db_session):
    await _seed_minimal(db_session)
    from scripts.build_kg import derive_from_modern_evidence
    edges = await derive_from_modern_evidence(db_session)
    assert len(edges) == 1
    assert edges[0].predicate == "has_evidence"
    assert edges[0].source_kind == "dravya"
    assert edges[0].target_kind == "modern_evidence"


async def test_dedupe_collapses_duplicate_signatures():
    """Multiple sources may emit the same edge — dedupe must collapse them."""
    from scripts.build_kg import _dedupe_edges, _edge
    a = _edge("indicated_for", "dravya", None, "X", "vyadhi", None, "Y")
    b = _edge("indicated_for", "dravya", None, "X", "vyadhi", None, "Y")
    out = _dedupe_edges([a, b])
    assert len(out) == 1


# ---- query helpers ---------------------------------------------------


async def test_neighbors_groups_by_predicate(db_session):
    """End-to-end: build full KG from a tiny seed, query neighbors.
    Multiple derivers can emit the same (src, predicate, tgt) edge — for
    example Yogarāja Guggulu→Āmavāta is reachable both from
    Formulation.indications and Vyadhi.common_formulations. The pipeline
    deduplicates before commit; the test does the same."""
    seeded = await _seed_minimal(db_session)
    from scripts.build_kg import (
        derive_from_formulations, derive_from_vyadhi,
        derive_from_procedures, derive_from_diagnostic_patterns,
        derive_from_modern_evidence, _dedupe_edges,
    )
    resolvers = await kg_service.get_kg_resolvers(db_session)
    edges = []
    edges.extend(await derive_from_formulations(db_session, resolvers))
    edges.extend(await derive_from_vyadhi(db_session, resolvers))
    edges.extend(await derive_from_procedures(db_session, resolvers))
    edges.extend(await derive_from_diagnostic_patterns(db_session, resolvers))
    edges.extend(await derive_from_modern_evidence(db_session))
    for e in _dedupe_edges(edges):
        db_session.add(e)
    await db_session.commit()

    grouped = await kg_service.neighbors(db_session, "vyadhi", seeded["vyadhi"].id)
    # Āmavāta should be reachable via 'indicated_for' (in-edges from
    # Aśvagandhā/Yogarāja/Kaṭi Basti) and 'diagnoses' (in-edge from pattern).
    assert "indicated_for" in grouped
    assert "diagnoses" in grouped
    assert all(e["direction"] == "in" for e in grouped["indicated_for"])


async def test_neighbors_direction_filter(db_session):
    seeded = await _seed_minimal(db_session)
    from scripts.build_kg import derive_from_diagnostic_patterns
    resolvers = await kg_service.get_kg_resolvers(db_session)
    for e in await derive_from_diagnostic_patterns(db_session, resolvers):
        db_session.add(e)
    await db_session.commit()

    out = await kg_service.neighbors(
        db_session, "diagnostic_pattern", seeded["pattern"].id, direction="out"
    )
    # Pattern's outgoing edges: 'diagnoses' + 'suggests_chikitsa'
    assert "diagnoses" in out
    assert "suggests_chikitsa" in out
    for edges in out.values():
        for e in edges:
            assert e["direction"] == "out"


async def test_subgraph_expands_to_depth_2(db_session):
    """Vyādhi → procedures (depth 1) → dravyas/formulations (depth 2)."""
    seeded = await _seed_minimal(db_session)
    from scripts.build_kg import (
        derive_from_formulations, derive_from_vyadhi,
        derive_from_procedures, derive_from_diagnostic_patterns,
        _dedupe_edges,
    )
    resolvers = await kg_service.get_kg_resolvers(db_session)
    edges = []
    for fn in (derive_from_formulations, derive_from_vyadhi,
               derive_from_procedures, derive_from_diagnostic_patterns):
        edges.extend(await fn(db_session, resolvers))
    for e in _dedupe_edges(edges):
        db_session.add(e)
    await db_session.commit()

    sub = await kg_service.subgraph(
        db_session, "vyadhi", seeded["vyadhi"].id, depth=2
    )
    kinds_seen = {n["kind"] for n in sub["nodes"]}
    # Should reach at least dravya/formulation/procedure within 2 hops
    assert {"dravya", "formulation", "procedure"} <= kinds_seen


async def test_subgraph_predicate_filter(db_session):
    seeded = await _seed_minimal(db_session)
    from scripts.build_kg import derive_from_vyadhi, derive_from_procedures
    resolvers = await kg_service.get_kg_resolvers(db_session)
    for e in await derive_from_vyadhi(db_session, resolvers):
        db_session.add(e)
    for e in await derive_from_procedures(db_session, resolvers):
        db_session.add(e)
    await db_session.commit()

    sub = await kg_service.subgraph(
        db_session, "vyadhi", seeded["vyadhi"].id, depth=2,
        predicates=["indicated_for"],
    )
    assert all(e["predicate"] == "indicated_for" for e in sub["edges"])
