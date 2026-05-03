"""Retrieval service tests — source filtering, dense vs hybrid, empty corpus."""
import pytest

from app.models import CorpusChunk
from app.services.retrieval import retrieve


@pytest.fixture
async def seeded_corpus(db_session, stub_embedding):
    """Insert a small synthetic corpus into the in-memory DB."""
    chunks = [
        CorpusChunk(
            source="Ashtanga Hridaya",
            section="Sutrasthana",
            chapter="Ch.2 Dinacharya",
            verse_start="2.7",
            sanskrit="abhyangam",
            english="One should perform abhyanga daily — pacifies vata, slows aging.",
            summary="abhyanga oil massage daily routine",
            embedding=stub_embedding("abhyanga daily oil massage routine"),
            embedding_model="stub",
        ),
        CorpusChunk(
            source="Ashtanga Hridaya",
            section="Sutrasthana",
            chapter="Ch.1 Ayushkamiya",
            verse_start="1.6",
            verse_end="1.7",
            sanskrit="trayo doshah",
            english="Vata Pitta Kapha — three doshas; balanced sustains, disturbed harms.",
            summary="three doshas vata pitta kapha balance",
            embedding=stub_embedding("three doshas vata pitta kapha"),
            embedding_model="stub",
        ),
        CorpusChunk(
            source="Charaka Samhita",
            section="Sutrasthana",
            chapter="Ch.1 Dirghanjivitiya",
            verse_start="1.41",
            sanskrit="samadoshah samagnih",
            english="Health (svastha) — balanced doshas, balanced agni, serene mind.",
            summary="svastha definition health balanced doshas agni",
            embedding=stub_embedding("svastha health balanced doshas agni"),
            embedding_model="stub",
        ),
        CorpusChunk(
            source="Charaka Samhita",
            section="Sutrasthana",
            chapter="Ch.5 Matrashitiya",
            verse_start="5.3",
            sanskrit="matravad",
            english="Eat in proper measure — preserves digestive fire (agni).",
            summary="matrashitiya eating measure agni",
            embedding=stub_embedding("eating measure proper agni"),
            embedding_model="stub",
        ),
    ]
    for c in chunks:
        db_session.add(c)
    await db_session.commit()
    return chunks


async def test_retrieve_empty_query_returns_empty(db_session, stub_embedding):
    assert await retrieve(db_session, "") == []
    assert await retrieve(db_session, "   ") == []


async def test_retrieve_dense_returns_top_k(db_session, seeded_corpus):
    results = await retrieve(db_session, "abhyanga oil massage", k=2, strategy="dense")
    assert len(results) == 2
    # Top result should be the abhyanga chunk.
    assert results[0].chunk.verse_start == "2.7"


async def test_retrieve_hybrid_promotes_keyword_match(db_session, seeded_corpus):
    """BM25 should help find chunks where the user's term appears literally."""
    results = await retrieve(db_session, "abhyanga", k=3, strategy="hybrid")
    labels = [r.chunk.citation_label() for r in results]
    # Abhyanga chunk MUST be in top 3.
    assert any("2.7" in l for l in labels)


async def test_retrieve_source_filter_excludes_others(db_session, seeded_corpus):
    results = await retrieve(
        db_session, "doshas", k=5, sources=["Charaka Samhita"], strategy="hybrid"
    )
    sources = {r.chunk.source for r in results}
    assert sources == {"Charaka Samhita"}


async def test_retrieve_source_filter_with_list_of_one(db_session, seeded_corpus):
    results = await retrieve(
        db_session, "abhyanga", k=5, sources=["Ashtanga Hridaya"], strategy="hybrid"
    )
    sources = {r.chunk.source for r in results}
    assert sources == {"Ashtanga Hridaya"}


async def test_retrieve_no_source_match_returns_empty(db_session, seeded_corpus):
    results = await retrieve(
        db_session, "anything", k=5, sources=["Sushruta Samhita"], strategy="hybrid"
    )
    assert results == []


async def test_retrieve_returns_score_metadata(db_session, seeded_corpus):
    results = await retrieve(db_session, "abhyanga", k=2, strategy="hybrid")
    assert results
    r = results[0]
    assert r.score > 0
    # Hybrid carries both component scores.
    assert r.dense_score is not None
    assert r.bm25_score is not None


async def test_retrieve_tolerates_mixed_embedding_dims(db_session, stub_embedding):
    """Mid-migration the corpus may contain rows with different vector dims.
    Dense ranking must zero-out the mismatched rows rather than crash, so
    retrieval still works during the bge-m3 swap."""
    # Stub embeds at 16-dim; insert one chunk with a wrong-dim vector.
    db_session.add(CorpusChunk(
        source="X", chapter="1", verse_start="1",
        sanskrit="abhyangam", english="abhyanga",
        embedding=stub_embedding("abhyanga"),
        embedding_model="stub",
    ))
    db_session.add(CorpusChunk(
        source="X", chapter="1", verse_start="2",
        sanskrit="abhyangam", english="abhyanga",
        embedding=[0.1] * 999,  # wrong dim — must not crash retrieve
        embedding_model="legacy-model",
    ))
    await db_session.commit()

    results = await retrieve(db_session, "abhyanga", k=2, strategy="hybrid")
    assert results, "retrieval must succeed despite mixed dims"
    # The well-dimensioned chunk should rank above the zero-scored one on dense.
    top = results[0]
    assert top.chunk.verse_start == "1"
