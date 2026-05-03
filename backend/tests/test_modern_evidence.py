"""ModernEvidence model + PubMed parser + ingestion idempotency tests."""
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Dravya, ModernEvidence


# ---- model -------------------------------------------------------------


async def test_modern_evidence_inserts_with_full_schema(db_session):
    d = Dravya(nama_sanskrit="Aśvagandhā", latin_binomial="Withania somnifera")
    db_session.add(d)
    await db_session.commit()

    e = ModernEvidence(
        pmid="34567890",
        doi="10.1234/abc.001",
        source_db="pubmed",
        source_url="https://pubmed.ncbi.nlm.nih.gov/34567890/",
        title="Withania somnifera in generalized anxiety: an RCT",
        journal="J Ayurveda Integr Med",
        year=2021,
        authors=[{"last": "Smith", "first": "John", "initials": "J"}],
        pubtypes=["Randomized Controlled Trial", "Journal Article"],
        mesh_terms=["Anxiety", "Withania"],
        abstract_snippet="A double-blind RCT of W. somnifera vs placebo...",
        indication="anxiety",
        evidence_tier="B",
        dravya_id=d.id,
    )
    db_session.add(e)
    await db_session.commit()

    fetched = (await db_session.execute(
        select(ModernEvidence).where(ModernEvidence.pmid == "34567890")
    )).scalar_one()
    assert fetched.evidence_tier == "B"
    assert fetched.year == 2021
    assert fetched.authors[0]["last"] == "Smith"
    assert "Anxiety" in fetched.mesh_terms


async def test_modern_evidence_default_tier_is_C(db_session):
    d = Dravya(nama_sanskrit="Test", latin_binomial="Test test")
    db_session.add(d)
    await db_session.commit()
    e = ModernEvidence(pmid="1", title="t", dravya_id=d.id)
    db_session.add(e)
    await db_session.commit()
    fetched = (await db_session.execute(select(ModernEvidence))).scalar_one()
    assert fetched.evidence_tier == "C"
    assert fetched.source_db == "pubmed"


async def test_modern_evidence_unique_constraint_on_pmid_dravya(db_session):
    """Same PMID for the same dravya must not duplicate (composite uniqueness)."""
    d = Dravya(nama_sanskrit="Test", latin_binomial="Test test")
    db_session.add(d)
    await db_session.commit()

    db_session.add(ModernEvidence(pmid="1", title="t", dravya_id=d.id))
    await db_session.commit()

    db_session.add(ModernEvidence(pmid="1", title="t-again", dravya_id=d.id))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_modern_evidence_same_pmid_can_attach_to_multiple_dravyas(db_session):
    """One Triphalā paper attaches to three dravya rows — by design."""
    d1 = Dravya(nama_sanskrit="Harītakī", latin_binomial="Terminalia chebula")
    d2 = Dravya(nama_sanskrit="Vibhītakī", latin_binomial="Terminalia bellirica")
    db_session.add_all([d1, d2])
    await db_session.commit()

    db_session.add(ModernEvidence(pmid="999", title="Triphala study", dravya_id=d1.id))
    db_session.add(ModernEvidence(pmid="999", title="Triphala study", dravya_id=d2.id))
    await db_session.commit()

    rows = (await db_session.execute(
        select(ModernEvidence).where(ModernEvidence.pmid == "999")
    )).scalars().all()
    assert len(rows) == 2


# ---- tier_for_pubtypes ------------------------------------------------


def test_tier_a_for_meta_analysis():
    from scripts.ingest_pubmed import tier_for_pubtypes
    assert tier_for_pubtypes(["Meta-Analysis", "Journal Article"]) == "A"
    assert tier_for_pubtypes(["Systematic Review"]) == "A"


def test_tier_b_for_rct():
    from scripts.ingest_pubmed import tier_for_pubtypes
    assert tier_for_pubtypes(["Randomized Controlled Trial"]) == "B"


def test_tier_c_for_observational():
    from scripts.ingest_pubmed import tier_for_pubtypes
    assert tier_for_pubtypes(["Observational Study"]) == "C"
    assert tier_for_pubtypes(["Clinical Trial, Phase II"]) == "C"


def test_tier_d_for_review_only():
    from scripts.ingest_pubmed import tier_for_pubtypes
    assert tier_for_pubtypes(["Editorial"]) == "D"
    assert tier_for_pubtypes([]) == "D"


def test_build_query_clinical_only_includes_humans_and_pubtype_filter():
    """Default search must restrict to humans + clinical pubtypes —
    without this filter, recent-sort returns mostly in-silico/preclinical."""
    from scripts.ingest_pubmed import _build_query
    q = _build_query("Withania somnifera", clinical_only=True)
    assert '"Withania somnifera"[Title/Abstract]' in q
    assert "humans[Filter]" in q
    assert "Randomized Controlled Trial[ptyp]" in q
    assert "Systematic Review[ptyp]" in q
    assert "Meta-Analysis[ptyp]" in q


def test_build_query_without_clinical_only_drops_filter():
    from scripts.ingest_pubmed import _build_query
    q = _build_query("Curcuma longa", clinical_only=False)
    assert "humans[Filter]" not in q
    assert "ptyp" not in q


def test_tier_a_dominates_over_b_when_both_present():
    """A Cochrane SR can be tagged both 'Systematic Review' and 'Review' —
    tier A wins."""
    from scripts.ingest_pubmed import tier_for_pubtypes
    assert tier_for_pubtypes(["Systematic Review", "Review"]) == "A"


# ---- XML parser -------------------------------------------------------


SAMPLE_XML = b"""<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>34567890</PMID>
      <Article>
        <Journal>
          <Title>Journal of Ayurveda and Integrative Medicine</Title>
          <ISOAbbreviation>J Ayurveda Integr Med</ISOAbbreviation>
        </Journal>
        <ArticleTitle>Effect of Withania somnifera on anxiety: a randomized trial</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND">Anxiety is a common condition.</AbstractText>
          <AbstractText Label="METHODS">Double-blind RCT, n=120.</AbstractText>
          <AbstractText Label="RESULTS">Significant reduction (p&lt;0.01).</AbstractText>
        </Abstract>
        <AuthorList>
          <Author>
            <LastName>Sharma</LastName>
            <ForeName>Rajiv</ForeName>
            <Initials>R</Initials>
          </Author>
          <Author>
            <LastName>Iyer</LastName>
            <ForeName>Maya</ForeName>
            <Initials>M</Initials>
          </Author>
        </AuthorList>
        <PublicationTypeList>
          <PublicationType>Randomized Controlled Trial</PublicationType>
          <PublicationType>Journal Article</PublicationType>
        </PublicationTypeList>
        <ArticleDate><Year>2022</Year></ArticleDate>
      </Article>
      <MeshHeadingList>
        <MeshHeading><DescriptorName>Anxiety</DescriptorName></MeshHeading>
        <MeshHeading><DescriptorName>Withania</DescriptorName></MeshHeading>
      </MeshHeadingList>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">34567890</ArticleId>
        <ArticleId IdType="doi">10.1016/j.jaim.2022.01.001</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>11111111</PMID>
      <Article>
        <Journal><Title>Phytomedicine</Title></Journal>
        <ArticleTitle>A systematic review and meta-analysis of W. somnifera</ArticleTitle>
        <PublicationTypeList>
          <PublicationType>Systematic Review</PublicationType>
          <PublicationType>Meta-Analysis</PublicationType>
        </PublicationTypeList>
        <PubDate><Year>2023</Year></PubDate>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""


def test_parse_efetch_xml_extracts_two_papers():
    from scripts.ingest_pubmed import parse_efetch_xml
    rows = parse_efetch_xml(SAMPLE_XML)
    assert len(rows) == 2

    rct = next(r for r in rows if r["pmid"] == "34567890")
    assert rct["title"].startswith("Effect of Withania")
    assert rct["doi"] == "10.1016/j.jaim.2022.01.001"
    assert rct["year"] == 2022
    assert rct["journal"] == "Journal of Ayurveda and Integrative Medicine"
    assert rct["evidence_tier"] == "B"
    assert "Randomized Controlled Trial" in rct["pubtypes"]
    assert rct["mesh_terms"] == ["Anxiety", "Withania"]
    assert len(rct["authors"]) == 2
    assert rct["authors"][0]["last"] == "Sharma"
    assert rct["abstract_snippet"].startswith("BACKGROUND:")
    assert rct["source_url"] == "https://pubmed.ncbi.nlm.nih.gov/34567890/"


def test_parse_efetch_xml_tiers_meta_analysis_as_A():
    from scripts.ingest_pubmed import parse_efetch_xml
    rows = parse_efetch_xml(SAMPLE_XML)
    sr = next(r for r in rows if r["pmid"] == "11111111")
    assert sr["evidence_tier"] == "A"
    assert sr["year"] == 2023


def test_parse_efetch_xml_handles_empty():
    from scripts.ingest_pubmed import parse_efetch_xml
    assert parse_efetch_xml(b"") == []
    assert parse_efetch_xml(b"<PubmedArticleSet></PubmedArticleSet>") == []


def test_abstract_snippet_capped_at_500_chars():
    from scripts.ingest_pubmed import parse_efetch_xml
    long_text = "x" * 1000
    xml = f"""<?xml version="1.0"?>
<PubmedArticleSet><PubmedArticle><MedlineCitation>
  <PMID>1</PMID>
  <Article>
    <Journal><Title>J</Title></Journal>
    <ArticleTitle>T</ArticleTitle>
    <Abstract><AbstractText>{long_text}</AbstractText></Abstract>
    <PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList>
  </Article>
</MedlineCitation></PubmedArticle></PubmedArticleSet>
""".encode()
    rows = parse_efetch_xml(xml)
    assert len(rows[0]["abstract_snippet"]) == 500


def test_parser_handles_medline_date_format():
    """PubMed sometimes uses MedlineDate like '2018 Jan-Feb' instead of Year."""
    from scripts.ingest_pubmed import parse_efetch_xml
    xml = b"""<?xml version="1.0"?>
<PubmedArticleSet><PubmedArticle><MedlineCitation>
  <PMID>2</PMID>
  <Article>
    <Journal><Title>J</Title><JournalIssue><PubDate><MedlineDate>2018 Jan-Feb</MedlineDate></PubDate></JournalIssue></Journal>
    <ArticleTitle>T</ArticleTitle>
    <PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList>
  </Article>
</MedlineCitation></PubmedArticle></PubmedArticleSet>
"""
    rows = parse_efetch_xml(xml)
    assert rows[0]["year"] == 2018


# ---- ingestion idempotency -------------------------------------------


async def test_upsert_evidence_inserts_then_updates(db_session):
    from scripts.ingest_pubmed import upsert_evidence

    d = Dravya(nama_sanskrit="Aśvagandhā", latin_binomial="Withania somnifera")
    db_session.add(d)
    await db_session.commit()

    parsed = {
        "pmid": "1",
        "doi": None,
        "source_db": "pubmed",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/1/",
        "title": "Original title",
        "journal": "J",
        "year": 2020,
        "authors": None,
        "pubtypes": ["Journal Article"],
        "mesh_terms": None,
        "abstract_snippet": None,
        "evidence_tier": "C",
    }

    out1 = await upsert_evidence(db_session, parsed, d.id, indication_hint=None)
    await db_session.commit()
    assert out1 == "inserted"

    parsed["title"] = "Updated title"
    parsed["evidence_tier"] = "B"
    out2 = await upsert_evidence(db_session, parsed, d.id, indication_hint="anxiety")
    await db_session.commit()
    assert out2 == "updated"

    rows = (await db_session.execute(
        select(ModernEvidence).where(ModernEvidence.dravya_id == d.id)
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].title == "Updated title"
    assert rows[0].evidence_tier == "B"
    assert rows[0].indication == "anxiety"
