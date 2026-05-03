"""Tiny pure-Python BM25 for the classical-text corpus.

No external dependency — at corpus sizes up to a few thousand chunks the
overhead is negligible and avoiding `rank_bm25` keeps the deploy footprint
clean. The tokenizer is Unicode-aware (`\\w+` matches Devanagari out of the
box in Python), so Sanskrit terms in the user query land on the same
tokens as Sanskrit terms in the chunks.

Scoring follows the standard BM25 formulation (k1=1.5, b=0.75 — Lucene
defaults). When the corpus grows past a few tens of thousands of chunks,
swap this for a precomputed inverted index or move to Postgres FTS.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Sequence


# Token regex needs to keep Devanagari clusters intact. Python's `\w` alone
# matches consonants + vowels but NOT the combining marks (halant ्, vowel
# signs ा ि ी ु ू, anusvara ं, etc), so "क्या" would split into "क" + "य".
# Extending the character class with the full Devanagari block (U+0900-U+097F)
# makes a single token of any contiguous Devanagari run.
_TOKEN_RE = re.compile(r"[\wऀ-ॿ]+", re.UNICODE)

# Stop words filtered from BM25 queries AND documents. Without this, common
# words like "what" / "is" / "के" rack up positive IDF from the +1 in the
# Lucene formula and dominate scoring for short conversational queries.
# Keeping this list small and conservative — domain terms ("body", "life")
# stay in. Add Hindi negation/quantifiers as needed.
_STOP_WORDS = frozenset({
    # English function words
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "of", "in", "on", "at", "to", "for", "with", "by", "from", "as",
    "and", "or", "but", "if", "then", "else", "so", "than",
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "it", "they",
    "what", "which", "who", "whom", "whose", "where", "when", "why", "how",
    "this", "that", "these", "those",
    "do", "does", "did", "doing",
    "have", "has", "had", "having",
    "should", "would", "could", "can", "may", "might", "must", "shall", "will",
    "not", "no", "nor",
    "about", "tell", "say", "says", "said", "ask", "please",
    # Hindi function particles (Devanagari)
    "का", "के", "की", "को", "में", "से", "है", "हैं", "हो", "हुआ",
    "और", "या", "पर", "तो", "ही", "भी", "नहीं",
    "क्या", "कैसे", "क्यों", "कौन", "कब", "कहां",
    "मैं", "मेरा", "हम", "तुम", "वह", "यह",
})


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP_WORDS]


def bm25_scores(
    query: str,
    documents: Sequence[str],
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    """Return BM25 score per document for the given query.

    Parameters
    ----------
    query : str
    documents : sequence of str
        Document texts to score.
    k1, b : BM25 hyperparameters (Lucene defaults: 1.5, 0.75).
    """
    query_tokens = tokenize(query)
    if not query_tokens or not documents:
        return [0.0] * len(documents)

    doc_tokens: list[list[str]] = [tokenize(d) for d in documents]
    n_docs = len(doc_tokens)
    avgdl = sum(len(d) for d in doc_tokens) / n_docs if n_docs else 1.0
    if avgdl == 0:
        return [0.0] * n_docs

    # Document frequency for query terms only — saves work on large vocab.
    df: Counter[str] = Counter()
    query_term_set = set(query_tokens)
    for tokens in doc_tokens:
        present = query_term_set.intersection(tokens)
        for t in present:
            df[t] += 1

    # Pre-compute IDF per query term.
    idf: dict[str, float] = {}
    for term in query_term_set:
        if term not in df:
            continue
        idf[term] = math.log((n_docs - df[term] + 0.5) / (df[term] + 0.5) + 1)

    scores: list[float] = []
    for tokens in doc_tokens:
        dl = len(tokens)
        if dl == 0:
            scores.append(0.0)
            continue
        tf = Counter(tokens)
        score = 0.0
        norm = 1 - b + b * dl / avgdl
        for term in query_tokens:
            f = tf.get(term)
            if not f:
                continue
            term_idf = idf.get(term)
            if term_idf is None:
                continue
            score += term_idf * (f * (k1 + 1)) / (f + k1 * norm)
        scores.append(score)
    return scores


def reciprocal_rank_fusion(
    ranked_id_lists: Sequence[Sequence],
    k: int = 60,
) -> dict:
    """Reciprocal Rank Fusion across multiple ranked id lists.

    Each input is a list of doc ids ordered best-first. Returns a dict of
    {id: fused_score}. Items absent from a list contribute nothing for that
    list — which is the desired behaviour for hybrid retrieval (a doc that
    appears only in the dense top-K still gets credit, just less than a doc
    that appears in both).
    """
    fused: dict = {}
    for ranked in ranked_id_lists:
        for rank, item_id in enumerate(ranked):
            fused[item_id] = fused.get(item_id, 0.0) + 1.0 / (k + rank + 1)
    return fused
