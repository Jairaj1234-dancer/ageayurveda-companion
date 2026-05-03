"""BM25 unit tests — tokenization, stop words, scoring, fusion."""
from app.services.bm25 import bm25_scores, reciprocal_rank_fusion, tokenize


def test_tokenize_lowercases_and_strips_punct():
    assert tokenize("Hello, World!") == ["hello", "world"]


def test_tokenize_drops_english_stop_words():
    # "what" / "is" are stops; "abhyanga" is not.
    assert tokenize("What is abhyanga?") == ["abhyanga"]


def test_tokenize_drops_hindi_stop_words():
    # क्या/है are stops; दिनचर्या survives.
    assert tokenize("क्या है दिनचर्या") == ["दिनचर्या"]


def test_tokenize_handles_devanagari():
    tokens = tokenize("अभ्यंग")
    assert tokens == ["अभ्यंग"]


def test_tokenize_empty_input():
    assert tokenize("") == []
    assert tokenize(None) == []  # type: ignore[arg-type]


def test_bm25_ranks_keyword_match_above_unrelated():
    docs = [
        "abhyanga is daily oil massage",
        "the seven dhatus are tissues",
        "morning routine and evening routine",
    ]
    scores = bm25_scores("abhyanga", docs)
    assert scores[0] > scores[1]
    assert scores[0] > scores[2]


def test_bm25_zero_for_no_match():
    scores = bm25_scores("vimochana", ["foo bar", "baz quux"])
    assert all(s == 0.0 for s in scores)


def test_bm25_handles_empty_docs():
    assert bm25_scores("anything", []) == []


def test_bm25_stop_words_dont_dominate():
    """Without stop-word filtering, "what is X" would let common terms in
    every doc rack up score and drown out the real signal term X. With the
    filter, only X drives the ranking."""
    docs = [
        "what is happening today",  # common words only
        "abhyanga is a practice",  # contains the signal term
        "what is what is what is",  # gibberish, all stops
    ]
    scores = bm25_scores("what is abhyanga", docs)
    assert scores[1] > scores[0]
    assert scores[1] > scores[2]


def test_rrf_fusion_combines_lists():
    # Doc 'a' is rank 0 in list 1 and rank 2 in list 2 → high fused score.
    # Doc 'd' is rank 1 in list 1 only → moderate score.
    # Doc 'z' is in neither → score 0 (not present).
    fused = reciprocal_rank_fusion(
        [["a", "d", "x"], ["b", "c", "a"]],
        k=5,
    )
    assert fused["a"] > fused["d"]
    assert fused["a"] > fused["b"]
    assert fused["a"] > fused["c"]
    assert "z" not in fused


def test_rrf_fusion_empty_lists():
    assert reciprocal_rank_fusion([]) == {}
    assert reciprocal_rank_fusion([[], []]) == {}
