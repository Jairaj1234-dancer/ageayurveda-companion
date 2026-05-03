"""Re-embed-corpus script tests — selection, batch update, idempotency.

Embedding inference is stubbed via the existing `stub_embedding` fixture,
so these run in well under a second."""
import pytest
from sqlalchemy import select

from app.models import CorpusChunk


def _make_chunk(model: str, idx: int = 0) -> CorpusChunk:
    return CorpusChunk(
        source="Test",
        chapter="1",
        verse_start=str(idx),
        verse_end=str(idx),
        sanskrit=f"verse {idx}",
        transliteration=f"verse {idx}",
        english=f"english {idx}",
        embedding=[0.1] * 16,
        embedding_model=model,
        language="multi",
    )


# ---- selection --------------------------------------------------------


async def test_select_stale_picks_only_old_model(db_session):
    from scripts.reembed_corpus import _select_stale, _count_stale

    db_session.add(_make_chunk("old-model", 1))
    db_session.add(_make_chunk("old-model", 2))
    db_session.add(_make_chunk("new-model", 3))
    await db_session.commit()

    n_stale = await _count_stale(db_session, "new-model")
    assert n_stale == 2

    stale = await _select_stale(db_session, "new-model", limit=None)
    assert len(stale) == 2
    assert all(c.embedding_model == "old-model" for c in stale)


async def test_select_stale_respects_limit(db_session):
    from scripts.reembed_corpus import _select_stale

    for i in range(5):
        db_session.add(_make_chunk("old-model", i))
    await db_session.commit()

    stale = await _select_stale(db_session, "new-model", limit=2)
    assert len(stale) == 2


async def test_count_stale_is_zero_when_all_match(db_session):
    from scripts.reembed_corpus import _count_stale

    for i in range(3):
        db_session.add(_make_chunk("new-model", i))
    await db_session.commit()

    assert await _count_stale(db_session, "new-model") == 0


# ---- _embed_text_for_chunk -------------------------------------------


def test_embed_text_concatenates_available_fields():
    from scripts.reembed_corpus import _embed_text_for_chunk

    c = CorpusChunk(
        source="X", sanskrit="स", transliteration="sa",
        english="being", embedding=[], embedding_model="x",
    )
    text = _embed_text_for_chunk(c)
    assert "स" in text
    assert "sa" in text
    assert "being" in text


def test_embed_text_falls_back_to_citation_label_when_empty():
    from scripts.reembed_corpus import _embed_text_for_chunk

    c = CorpusChunk(
        source="Caraka", chapter="1", verse_start="1",
        embedding=[], embedding_model="x",
    )
    text = _embed_text_for_chunk(c)
    assert "Caraka" in text


# ---- reembed_batch ----------------------------------------------------


async def test_reembed_batch_updates_vector_and_model(db_session, stub_embedding):
    from scripts.reembed_corpus import reembed_batch

    chunks = [_make_chunk("old-model", i) for i in range(3)]
    db_session.add_all(chunks)
    await db_session.commit()

    n = await reembed_batch(db_session, chunks, "new-model")
    await db_session.commit()
    assert n == 3

    fetched = (await db_session.execute(select(CorpusChunk))).scalars().all()
    assert all(c.embedding_model == "new-model" for c in fetched)
    # Stub embedding returns a 16-d hash-vector, distinct from the placeholder.
    assert all(len(c.embedding) == 16 for c in fetched)


async def test_reembed_batch_is_idempotent(db_session, stub_embedding):
    """Running the batch a second time on already-updated rows is a no-op
    in terms of correctness — the model tag already matches and selection
    will return them as already-current.

    We verify here that calling reembed_batch directly twice produces the
    same final state (vectors deterministic from stub, model tag stable).
    """
    from scripts.reembed_corpus import reembed_batch

    chunks = [_make_chunk("old-model", i) for i in range(2)]
    db_session.add_all(chunks)
    await db_session.commit()

    await reembed_batch(db_session, chunks, "new-model")
    await db_session.commit()
    first_vectors = [list(c.embedding) for c in chunks]

    await reembed_batch(db_session, chunks, "new-model")
    await db_session.commit()
    second_vectors = [list(c.embedding) for c in chunks]

    assert first_vectors == second_vectors


async def test_reembed_batch_handles_empty_list(db_session, stub_embedding):
    from scripts.reembed_corpus import reembed_batch
    n = await reembed_batch(db_session, [], "new-model")
    assert n == 0
