"""Citation extractor tests. Locks down the regex contract that grounded_chat
relies on for citation rendering and the widget for chip rendering."""
from app.services.citation import extract_citations, format_citation_label


def test_extract_simple_citation():
    text = "According to [Charaka Samhita, Sutra Sthana 1:42], health is balance."
    cites = extract_citations(text)
    assert len(cites) == 1
    assert cites[0]["source"] == "Charaka Samhita"
    assert cites[0]["chapter"] == "Sutra Sthana"
    assert cites[0]["verse"] == "1:42"


def test_extract_ashtanga_hridaya_with_chapter_name():
    text = "[Ashtanga Hridaya, Sutrasthana, Ch.2 verse 7] discusses abhyanga."
    cites = extract_citations(text)
    assert len(cites) == 1
    assert cites[0]["source"] == "Ashtanga Hridaya"


def test_extract_multiple_citations_dedupes():
    text = (
        "[Charaka Samhita, Sutrasthana 1:41] "
        "and again [Charaka Samhita, Sutrasthana 1:41] "
        "and [Ashtanga Hridaya, Sutrasthana 2:7]"
    )
    cites = extract_citations(text)
    assert len(cites) == 2
    sources = sorted(c["source"] for c in cites)
    assert sources == ["Ashtanga Hridaya", "Charaka Samhita"]


def test_extract_no_match_returns_empty():
    text = "No citations here, just prose."
    assert extract_citations(text) == []


def test_extract_ignores_non_classical_brackets():
    text = "See [Wikipedia article] for more, but [Charaka Samhita 1:1] is canonical."
    cites = extract_citations(text)
    assert len(cites) == 1
    assert cites[0]["source"] == "Charaka Samhita"


def test_format_citation_label():
    label = format_citation_label({
        "source": "Ashtanga Hridaya",
        "chapter_name": "Sutrasthana",
        "verse_start": "2.7",
        "verse_end": "2.7",
    })
    assert "Ashtanga Hridaya" in label
    assert "Sutrasthana" in label
    assert "2.7" in label


def test_format_citation_label_range():
    label = format_citation_label({
        "source": "Ashtanga Hridaya",
        "chapter": "Ch.1",
        "verse_start": "1.6",
        "verse_end": "1.7",
    })
    assert "1.6-1.7" in label
