"""Wikidata enrichment — query construction, response parsing, diff logic."""
import pytest
from sqlalchemy import select

from app.models import Dravya


# ---- query construction -----------------------------------------------


def test_query_includes_latin_and_synonym_union():
    from scripts.enrich_wikidata import build_taxon_query
    q = build_taxon_query("Withania somnifera")
    # Both the canonical-name and synonym branches must be present so we can
    # find dravyas that the seed encoded under an older synonym.
    assert 'wdt:P225 "Withania somnifera"' in q
    assert "P1420" in q  # taxon synonym
    assert "P171*" in q  # transitive parent
    assert "wd:Q35409" in q  # family rank


def test_query_escapes_double_quotes():
    """Defensive: latin binomials never contain quotes, but escape just in case."""
    from scripts.enrich_wikidata import build_taxon_query
    q = build_taxon_query('Foo "bar" baz')
    assert '"Foo \\"bar\\" baz"' in q


# ---- candidate binomials ----------------------------------------------


def test_candidate_strips_parens():
    from scripts.enrich_wikidata import candidate_binomials
    cands = candidate_binomials("Zingiber officinale (dried)")
    assert "Zingiber officinale" in cands


def test_candidate_splits_slash():
    from scripts.enrich_wikidata import candidate_binomials
    cands = candidate_binomials("Cinnamomum verum / C. zeylanicum")
    assert "Cinnamomum verum" in cands
    assert "Cinnamomum zeylanicum" in cands


def test_candidate_expands_abbreviated_genus():
    """'Eclipta alba / E. prostrata' → also try 'Eclipta prostrata'."""
    from scripts.enrich_wikidata import candidate_binomials
    cands = candidate_binomials("Eclipta alba / E. prostrata")
    assert "Eclipta alba" in cands
    assert "Eclipta prostrata" in cands


def test_candidate_first_is_original():
    from scripts.enrich_wikidata import candidate_binomials
    cands = candidate_binomials("Withania somnifera")
    assert cands[0] == "Withania somnifera"


# ---- response parsing -------------------------------------------------


_FULL_BINDING = {
    "results": {
        "bindings": [
            {
                "taxon": {"value": "http://www.wikidata.org/entity/Q282569"},
                "canonicalName": {"value": "Withania somnifera"},
                "familyName": {"value": "Solanaceae"},
            }
        ]
    }
}


def test_parse_full_binding():
    from scripts.enrich_wikidata import parse_taxon_response
    out = parse_taxon_response(_FULL_BINDING)
    assert out == {
        "wikidata_qid": "Q282569",
        "canonical_latin_binomial": "Withania somnifera",
        "family": "Solanaceae",
    }


def test_parse_picks_binding_with_family_when_multiple():
    """If Wikidata returns multiple bindings, prefer one with familyName."""
    from scripts.enrich_wikidata import parse_taxon_response
    body = {
        "results": {
            "bindings": [
                {
                    "taxon": {"value": "http://www.wikidata.org/entity/Q1"},
                    "canonicalName": {"value": "X"},
                },
                {
                    "taxon": {"value": "http://www.wikidata.org/entity/Q2"},
                    "canonicalName": {"value": "X"},
                    "familyName": {"value": "Solanaceae"},
                },
            ]
        }
    }
    out = parse_taxon_response(body)
    assert out["wikidata_qid"] == "Q2"
    assert out["family"] == "Solanaceae"


def test_parse_empty_returns_none():
    from scripts.enrich_wikidata import parse_taxon_response
    assert parse_taxon_response({"results": {"bindings": []}}) is None


def test_parse_missing_taxon_uri_returns_none():
    from scripts.enrich_wikidata import parse_taxon_response
    body = {"results": {"bindings": [{"canonicalName": {"value": "X"}}]}}
    assert parse_taxon_response(body) is None


# ---- diff logic -------------------------------------------------------


def test_diff_fills_missing_qid():
    from scripts.enrich_wikidata import diff_dravya
    d = Dravya(nama_sanskrit="Aśvagandhā", latin_binomial="Withania somnifera",
               family="Solanaceae")
    found = {"wikidata_qid": "Q282569",
             "canonical_latin_binomial": "Withania somnifera",
             "family": "Solanaceae"}
    out = diff_dravya(d, found, apply_family_fix=False)
    assert out == {"wikidata_qid": "Q282569"}


def test_diff_does_not_overwrite_curated_binomial():
    """If local already has a binomial set, Wikidata's canonical does not
    silently overwrite it — that should require human review."""
    from scripts.enrich_wikidata import diff_dravya
    d = Dravya(nama_sanskrit="X", latin_binomial="Old name",
               family="Y", wikidata_qid="Q9")
    found = {"wikidata_qid": "Q9",
             "canonical_latin_binomial": "New name",
             "family": "Y"}
    out = diff_dravya(d, found, apply_family_fix=False)
    assert "latin_binomial" not in out


def test_diff_fills_missing_binomial():
    from scripts.enrich_wikidata import diff_dravya
    d = Dravya(nama_sanskrit="X", latin_binomial=None)
    found = {"wikidata_qid": "Q9",
             "canonical_latin_binomial": "Genus species",
             "family": None}
    out = diff_dravya(d, found, apply_family_fix=False)
    assert out["latin_binomial"] == "Genus species"
    assert out["wikidata_qid"] == "Q9"


def test_diff_logs_family_disagreement_without_overwriting():
    """Default: if Wikidata's family disagrees, do NOT overwrite —
    the seed may be more accurate (some Ayurvedic plants use APG vs older
    classifications)."""
    from scripts.enrich_wikidata import diff_dravya
    d = Dravya(nama_sanskrit="X", latin_binomial="A b",
               family="OldFamily", wikidata_qid="Q1")
    found = {"wikidata_qid": "Q1",
             "canonical_latin_binomial": "A b",
             "family": "NewFamily"}
    out = diff_dravya(d, found, apply_family_fix=False)
    assert "family" not in out


def test_diff_applies_family_fix_when_explicit():
    from scripts.enrich_wikidata import diff_dravya
    d = Dravya(nama_sanskrit="X", latin_binomial="A b",
               family="OldFamily", wikidata_qid="Q1")
    found = {"wikidata_qid": "Q1",
             "canonical_latin_binomial": "A b",
             "family": "NewFamily"}
    out = diff_dravya(d, found, apply_family_fix=True)
    assert out["family"] == "NewFamily"


def test_diff_noop_when_everything_matches():
    from scripts.enrich_wikidata import diff_dravya
    d = Dravya(nama_sanskrit="X", latin_binomial="A b",
               family="F", wikidata_qid="Q1")
    found = {"wikidata_qid": "Q1",
             "canonical_latin_binomial": "A b",
             "family": "F"}
    assert diff_dravya(d, found, apply_family_fix=False) == {}


# ---- integration ------------------------------------------------------


async def test_enrich_one_writes_qid(db_session, monkeypatch):
    """End-to-end with the SPARQL POST stubbed."""
    import scripts.enrich_wikidata as ew

    d = Dravya(nama_sanskrit="Aśvagandhā", latin_binomial="Withania somnifera",
               family="Solanaceae")
    db_session.add(d)
    await db_session.commit()

    async def fake_lookup(client, latin):
        assert latin == "Withania somnifera"
        return {"wikidata_qid": "Q282569",
                "canonical_latin_binomial": "Withania somnifera",
                "family": "Solanaceae"}

    monkeypatch.setattr(ew, "lookup_taxon", fake_lookup)

    report = await ew.enrich_one(
        client=None, db=db_session, dravya=d,
        apply_family_fix=False, dry_run=False,
    )
    await db_session.commit()
    assert report["status"] == "updated"
    assert report["qid"] == "Q282569"

    fetched = (await db_session.execute(
        select(Dravya).where(Dravya.nama_sanskrit == "Aśvagandhā")
    )).scalar_one()
    assert fetched.wikidata_qid == "Q282569"


async def test_enrich_one_no_match_reports_cleanly(db_session, monkeypatch):
    import scripts.enrich_wikidata as ew

    d = Dravya(nama_sanskrit="X", latin_binomial="Nonexistent species")
    db_session.add(d)
    await db_session.commit()

    async def fake_lookup(client, latin):
        return None

    monkeypatch.setattr(ew, "lookup_taxon", fake_lookup)

    report = await ew.enrich_one(
        client=None, db=db_session, dravya=d,
        apply_family_fix=False, dry_run=False,
    )
    assert report["status"] == "no_match"
    assert report["found"] is False
