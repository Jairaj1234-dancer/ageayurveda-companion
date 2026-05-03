"""Unit tests for eval metrics — pure functions, no DB."""
import pytest

from app.services.eval.metrics import (
    citation_precision,
    citation_recall,
    hallucinated_citations,
    hit_at_k,
    is_refusal,
    mean,
    mean_reciprocal_rank,
    ndcg_at_k,
    recall_at_k,
    refusal_correctness,
)


# -- recall@k -------------------------------------------------------------


def test_recall_at_k_perfect():
    assert recall_at_k(["a", "b", "c"], {"a", "b"}, k=3) == 1.0


def test_recall_at_k_partial():
    assert recall_at_k(["a", "x", "y"], {"a", "b"}, k=3) == 0.5


def test_recall_at_k_none():
    assert recall_at_k(["x", "y"], {"a", "b"}, k=2) == 0.0


def test_recall_at_k_zero_when_gt_empty():
    assert recall_at_k(["a"], set(), k=1) == 0.0


def test_recall_at_k_truncates_predictions():
    # First 2 don't contain ground truth, so k=2 should miss
    assert recall_at_k(["x", "y", "a"], {"a"}, k=2) == 0.0
    assert recall_at_k(["x", "y", "a"], {"a"}, k=3) == 1.0


# -- hit@k ----------------------------------------------------------------


def test_hit_at_k_present():
    assert hit_at_k(["x", "a", "y"], {"a", "b"}, k=3) == 1.0


def test_hit_at_k_absent():
    assert hit_at_k(["x", "y", "z"], {"a", "b"}, k=3) == 0.0


def test_hit_at_k_just_outside_window():
    assert hit_at_k(["x", "y", "a"], {"a"}, k=2) == 0.0
    assert hit_at_k(["x", "y", "a"], {"a"}, k=3) == 1.0


# -- MRR ------------------------------------------------------------------


def test_mrr_first_position():
    assert mean_reciprocal_rank(["a", "b", "c"], {"a"}) == 1.0


def test_mrr_third_position():
    assert mean_reciprocal_rank(["x", "y", "a"], {"a"}) == pytest.approx(1 / 3)


def test_mrr_no_match():
    assert mean_reciprocal_rank(["x", "y"], {"a"}) == 0.0


# -- nDCG@k ---------------------------------------------------------------


def test_ndcg_perfect_ranking():
    rel = {"a": 1.0, "b": 1.0}
    # Perfect ranking — both relevant items at top
    s = ndcg_at_k(["a", "b", "c"], rel, k=3)
    assert s == pytest.approx(1.0)


def test_ndcg_reverse_ranking():
    rel = {"a": 1.0, "b": 1.0}
    s_perfect = ndcg_at_k(["a", "b", "c"], rel, k=3)
    s_swapped = ndcg_at_k(["c", "a", "b"], rel, k=3)
    # Same items but worse ranking — should be lower
    assert s_swapped < s_perfect


def test_ndcg_empty_relevance():
    assert ndcg_at_k(["a", "b"], {}, k=2) == 0.0


# -- citation precision/recall (ALCE) ------------------------------------


def test_citation_precision_all_grounded():
    cited = [
        {"source": "Charaka Saṃhitā", "section": "Sūtrasthāna", "verse": "41"},
        {"source": "Aṣṭāṅga Hṛdaya", "section": "Sūtrasthāna", "verse": "7"},
    ]
    retr = [
        {"source": "Charaka Saṃhitā", "section": "Sūtrasthāna", "verse_start": "41"},
        {"source": "Aṣṭāṅga Hṛdaya", "section": "Sūtrasthāna", "verse_start": "7"},
        {"source": "Suśruta Saṃhitā", "section": "Sūtrasthāna", "verse_start": "1"},
    ]
    assert citation_precision(cited, retr) == 1.0


def test_citation_precision_one_hallucinated():
    cited = [
        {"source": "Charaka Saṃhitā", "section": "Sūtrasthāna", "verse": "41"},
        {"source": "Charaka Saṃhitā", "section": "Sūtrasthāna", "verse": "9999"},
    ]
    retr = [{"source": "Charaka Saṃhitā", "section": "Sūtrasthāna", "verse_start": "41"}]
    assert citation_precision(cited, retr) == 0.5


def test_citation_precision_empty_is_one():
    """No citations = no opportunity to hallucinate (vacuous case)."""
    assert citation_precision([], [{"source": "x"}]) == 1.0


def test_hallucinated_citations_returns_invalid_only():
    cited = [
        {"source": "Charaka Saṃhitā", "section": "Sūtrasthāna", "verse": "41"},
        {"source": "FAKE", "section": "x", "verse": "1"},
    ]
    retr = [{"source": "Charaka Saṃhitā", "section": "Sūtrasthāna", "verse_start": "41"}]
    bad = hallucinated_citations(cited, retr)
    assert len(bad) == 1
    assert bad[0]["source"] == "FAKE"


def test_citation_recall_all_claims_grounded():
    claims = [
        {"claim_text": "...", "citations": [
            {"source": "Charaka Saṃhitā", "section": "Sūtrasthāna", "verse": "41"}
        ]},
        {"claim_text": "...", "citations": [
            {"source": "Aṣṭāṅga Hṛdaya", "section": "Sūtrasthāna", "verse": "7"}
        ]},
    ]
    retr = [
        {"source": "Charaka Saṃhitā", "section": "Sūtrasthāna", "verse_start": "41"},
        {"source": "Aṣṭāṅga Hṛdaya", "section": "Sūtrasthāna", "verse_start": "7"},
    ]
    assert citation_recall(claims, retr) == 1.0


def test_citation_recall_partial():
    claims = [
        {"citations": [{"source": "Charaka Saṃhitā", "section": "Sūtrasthāna", "verse": "41"}]},
        {"citations": [{"source": "FAKE", "section": "x", "verse": "1"}]},
    ]
    retr = [{"source": "Charaka Saṃhitā", "section": "Sūtrasthāna", "verse_start": "41"}]
    assert citation_recall(claims, retr) == 0.5


# -- refusal correctness --------------------------------------------------


def test_is_refusal_detects_emergency_marker():
    assert is_refusal("Please seek immediate medical attention.") is True


def test_is_refusal_detects_consult_marker():
    assert is_refusal("Please consult a qualified physician.") is True


def test_is_refusal_negative():
    assert is_refusal("Take 3g of Triphala daily.") is False


def test_refusal_correctness_all_correct():
    items = [
        {"expected_refusal": True, "response": "Seek immediate medical care."},
        {"expected_refusal": False, "response": "Try this herb daily."},
    ]
    assert refusal_correctness(items) == 1.0


def test_refusal_correctness_mixed():
    items = [
        {"expected_refusal": True, "response": "Take this herb."},  # incorrect: should refuse
        {"expected_refusal": False, "response": "Take this herb."},  # correct
    ]
    assert refusal_correctness(items) == 0.5


# -- mean ----------------------------------------------------------------


def test_mean_basic():
    assert mean([0.5, 1.0, 0.0]) == 0.5


def test_mean_empty_is_zero():
    assert mean([]) == 0.0
