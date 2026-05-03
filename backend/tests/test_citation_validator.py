"""Citation allowlist enforcement tests."""
from types import SimpleNamespace

import pytest

from app.services.citation_validator import validate_citations
from app.services.retrieval import Retrieval


def _chunk(source, section, chapter, verse_start, verse_end=None):
    """Build a minimal chunk-like object with the fields the validator reads."""
    return SimpleNamespace(
        source=source,
        section=section,
        chapter=chapter,
        verse_start=str(verse_start),
        verse_end=str(verse_end if verse_end is not None else verse_start),
    )


def _ret(chunk, score=0.5):
    return Retrieval(chunk=chunk, score=score)


def test_valid_citation_passes_through():
    text = "Per [Charaka Samhita, Sutrasthana 1:41], health is balance."
    retrievals = [_ret(_chunk("Charaka Samhita", "Sutrasthana", "Ch.1 Dirghanjivitiya", 41))]
    result = validate_citations(text, retrievals)
    assert result.invalid == []
    assert len(result.valid) == 1
    assert "Charaka Samhita" in result.cleaned_text


def test_hallucinated_citation_is_stripped():
    text = "According to [Charaka Samhita, Sutrasthana 99:99], the moon is made of cheese."
    retrievals = [_ret(_chunk("Charaka Samhita", "Sutrasthana", "Ch.1", 41))]
    result = validate_citations(text, retrievals)
    assert len(result.invalid) == 1
    assert result.invalid[0]["reason"] == "not in retrieval set"
    assert "[" not in result.cleaned_text
    # Prose around the citation must be preserved.
    assert "moon is made of cheese" in result.cleaned_text


def test_mixed_valid_and_hallucinated():
    text = (
        "Per [Charaka Samhita, Sutrasthana 1:41] health is balance, "
        "and [Charaka Samhita, Sutrasthana 99:99] is fabricated."
    )
    retrievals = [_ret(_chunk("Charaka Samhita", "Sutrasthana", "Ch.1", 41))]
    result = validate_citations(text, retrievals)
    assert len(result.valid) == 1
    assert len(result.invalid) == 1
    assert "[Charaka Samhita, Sutrasthana 1:41]" in result.cleaned_text
    assert "99:99" not in result.cleaned_text


def test_no_citations_in_text():
    text = "This is a plain answer without any citations."
    retrievals = [_ret(_chunk("Charaka Samhita", "Sutrasthana", "Ch.1", 41))]
    result = validate_citations(text, retrievals)
    assert result.valid == []
    assert result.invalid == []
    assert result.cleaned_text == text


def test_empty_retrieval_invalidates_everything():
    text = "Per [Charaka Samhita, Sutrasthana 1:41], health is balance."
    result = validate_citations(text, [])
    assert len(result.invalid) >= 1
    assert "[" not in result.cleaned_text


def test_diacritic_source_name_match():
    """Citation says 'Ashtanga Hridaya' (no diacritics); retrieval has
    'Aṣṭāṅga Hṛdaya' — should match via diacritic-stripping normaliser."""
    text = "See [Ashtanga Hridaya, Sutrasthana, Ch.2 verse 7]."
    retrievals = [_ret(_chunk("Aṣṭāṅga Hṛdaya", "Sūtrasthāna", "Ch.2 Dinacharyā", 7))]
    result = validate_citations(text, retrievals)
    assert len(result.valid) == 1
    assert len(result.invalid) == 0


def test_chapter_number_mismatch_invalidates():
    text = "See [Charaka Samhita, Sutrasthana, Ch.99 verse 1]."
    retrievals = [_ret(_chunk("Charaka Samhita", "Sutrasthana", "Ch.1", 1))]
    result = validate_citations(text, retrievals)
    assert len(result.invalid) == 1


def test_verse_range_overlap():
    """Citation Ch.1 verse 5; retrieval is verse_start=4, verse_end=8 — should match."""
    text = "Per [Charaka Samhita, Sutrasthana 1:5], …"
    retrievals = [_ret(_chunk("Charaka Samhita", "Sutrasthana", "Ch.1", 4, 8))]
    result = validate_citations(text, retrievals)
    assert len(result.valid) == 1


def test_verse_outside_range_invalidates():
    text = "Per [Charaka Samhita, Sutrasthana 1:99], …"
    retrievals = [_ret(_chunk("Charaka Samhita", "Sutrasthana", "Ch.1", 4, 8))]
    result = validate_citations(text, retrievals)
    assert len(result.invalid) == 1


def test_dedupes_repeated_valid_citations():
    text = (
        "[Charaka Samhita, Sutrasthana 1:41] and again "
        "[Charaka Samhita, Sutrasthana 1:41]"
    )
    retrievals = [_ret(_chunk("Charaka Samhita", "Sutrasthana", "Ch.1", 41))]
    result = validate_citations(text, retrievals)
    assert len(result.valid) == 1  # deduped
    assert len(result.invalid) == 0


def test_punctuation_tidied_after_strip():
    """Stripping '[FAKE]' from 'Hello, [FAKE].' should leave 'Hello,.' which we tidy."""
    text = "The texts say something. According to [Bhāvaprakāśa, Ch.99 verse 1] this is wrong, end."
    retrievals = [_ret(_chunk("Charaka Samhita", "Sutrasthana", "Ch.1", 41))]
    result = validate_citations(text, retrievals)
    # No double-spaces, no stranded punctuation.
    assert "  " not in result.cleaned_text
    assert ".," not in result.cleaned_text
