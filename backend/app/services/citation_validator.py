"""Citation allowlist enforcement — deterministic hallucination guard.

Every citation the LLM emits in the response text must point to a verse
that was actually in the retrieval set passed to the model. Any citation
that doesn't match a retrieval gets logged as a hallucination and
stripped from the user-visible text and the structured citations list.

This is the single highest-ROI safety guard in the platform — it cannot
prevent the model from making non-cited claims, but it can absolutely
prevent it from fabricating verse references. Recommended in the SOTA
retrieval research as "the single best hallucination guard"
(Self-RAG-style verification, but cheap and deterministic).

No LLM cost. Pure regex + set membership.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.logging import logger
from app.services.citation import extract_citations
from app.services.retrieval import Retrieval


# Match the same regex extract_citations uses, capturing the FULL bracket
# contents so we can strip them from the response text on invalidation.
_CITATION_BRACKET_RE = re.compile(
    r"\[([^\]]+(?:Samhita|Hridaya|Sangraha|Nidana|Prakasha|Ratnavali|Ratna)[^\]]*)\]",
    re.IGNORECASE,
)


@dataclass
class ValidatedCitations:
    cleaned_text: str
    valid: list[dict]
    invalid: list[dict]
    """invalid items have shape {raw_text, parsed_source, parsed_chapter,
    parsed_verse, reason}"""


# Map IAST diacritic letters to their conventional English-transliteration
# spellings so "Aṣṭāṅga" matches "Ashtanga", "Sūtrasthāna" matches
# "Sutrasthana", "Hṛdaya" matches "Hridaya", etc. NFKD alone would produce
# "Astanga" (no h), which fails to match the popular spelling.
_IAST_TO_ENGLISH = {
    "ṣ": "sh", "ś": "sh",
    "ṅ": "n", "ñ": "n", "ṇ": "n", "ṁ": "m", "ṃ": "m",
    "ṭ": "t", "ḍ": "d",
    "ṛ": "ri", "ṝ": "ri", "ḷ": "li",
    "ḥ": "h",
}


def _normalise(s: str | None) -> str:
    """Fuzzy-match-friendly normaliser:
    - applies IAST→English digraph substitutions
    - strips remaining combining diacritics
    - lower-cases, collapses whitespace + light punctuation
    """
    if not s:
        return ""
    import unicodedata
    out = s
    for ia, en in _IAST_TO_ENGLISH.items():
        out = out.replace(ia, en).replace(ia.upper(), en)
    nfkd = unicodedata.normalize("NFKD", out)
    ascii_form = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[\s,.:;]+", " ", ascii_form).strip().lower()


def _verse_overlaps(citation_verse: str | None, chunk_start: str | None, chunk_end: str | None) -> bool:
    """Does the citation's verse number overlap the chunk's verse range?

    Citations are flexible: "1:42", "1.42", "42", "1-7" all need to match
    a chunk with verse_start="42" and verse_end="42" (or ranges).
    """
    if not citation_verse:
        return True  # Citation didn't specify a verse — chapter-level match
    if not chunk_start:
        return False

    # Extract numbers from the citation verse.
    nums = re.findall(r"\d+", citation_verse)
    if not nums:
        return False
    cite_nums = [int(n) for n in nums]
    last = cite_nums[-1]

    try:
        cs = int(re.findall(r"\d+", chunk_start)[-1])
    except (IndexError, ValueError):
        return False
    try:
        ce = int(re.findall(r"\d+", chunk_end or chunk_start)[-1])
    except (IndexError, ValueError):
        ce = cs

    return cs <= last <= ce


def _split_chapter_and_verse(cite_chapter_norm: str, cite_verse: str | None) -> tuple[str | None, str | None]:
    """If the citation chapter holds 'Ch.X verse Y' (no comma split happened
    upstream), recover X as chapter and Y as verse so we don't conflate them
    when checking against the retrieval set.
    """
    if cite_verse is not None:
        return cite_chapter_norm, cite_verse

    # Look for "ch.<num>" first
    ch_match = re.search(r"ch\.?\s*(\d+)", cite_chapter_norm)
    if ch_match:
        chapter_num = ch_match.group(1)
        # Verse — anything after "verse" or after the chapter number
        v_match = re.search(r"verse\s*(\d+)", cite_chapter_norm)
        if not v_match:
            # Last number that isn't the chapter number
            tail = cite_chapter_norm[ch_match.end():]
            tail_nums = re.findall(r"\d+", tail)
            if tail_nums:
                return chapter_num, tail_nums[-1]
            return chapter_num, None
        return chapter_num, v_match.group(1)

    return cite_chapter_norm, cite_verse


def _citation_matches_retrieval(parsed: dict, retrievals: list[Retrieval]) -> bool:
    """True if any retrieval matches this parsed citation (source + chapter + verse)."""
    cite_source_norm = _normalise(parsed.get("source"))
    cite_chapter_norm = _normalise(parsed.get("chapter"))
    cite_verse_raw = parsed.get("verse")
    cite_chapter_norm, cite_verse = _split_chapter_and_verse(
        cite_chapter_norm, cite_verse_raw
    )

    for r in retrievals:
        chunk = r.chunk
        if cite_source_norm:
            chunk_source_norm = _normalise(chunk.source)
            # Match either direction (citation might use a shorter or longer name)
            if not (
                cite_source_norm in chunk_source_norm
                or chunk_source_norm in cite_source_norm
            ):
                continue

        # Chapter is a fuzzy gate. We require chapter-NUMBER agreement when
        # both sides supply one; ignore chapter-name spelling.
        if cite_chapter_norm:
            chunk_chapter_norm = _normalise(chunk.chapter)
            cite_ch_nums = re.findall(r"\d+", cite_chapter_norm)
            chunk_ch_nums = re.findall(r"\d+", chunk_chapter_norm or "")
            if cite_ch_nums and chunk_ch_nums:
                # Use the FIRST number from the citation chapter (the one
                # closest to "Ch." prefix), since later digits may belong
                # to a "verse N" tail that wasn't comma-split upstream.
                if cite_ch_nums[0] not in chunk_ch_nums:
                    continue

        if not _verse_overlaps(cite_verse, chunk.verse_start, chunk.verse_end):
            continue

        return True

    return False


def validate_citations(text: str, retrievals: list[Retrieval]) -> ValidatedCitations:
    """Strip invalid citations from text + return valid/invalid splits.

    Workflow:
      1. Find all `[Source, Section, Ch.X verse Y]` brackets in the text.
      2. Parse each via extract_citations.
      3. For each, check membership against the retrieval set.
      4. Strip invalid brackets from the output text (preserving the prose
         that surrounded them).
      5. Return both lists for logging + structured-response use.
    """
    if not text or not retrievals:
        # If no retrievals, every citation is unsupported by definition.
        # Still parse to log what got stripped.
        all_cites = extract_citations(text)
        cleaned = _CITATION_BRACKET_RE.sub("", text)
        return ValidatedCitations(
            cleaned_text=re.sub(r"\s{2,}", " ", cleaned).strip(),
            valid=[],
            invalid=[{**c, "reason": "no retrievals"} for c in all_cites],
        )

    valid: list[dict] = []
    invalid: list[dict] = []
    invalid_raw_brackets: list[str] = []

    # We iterate the regex matches directly so we can accumulate the raw
    # bracket strings to strip from the output text.
    for m in _CITATION_BRACKET_RE.finditer(text):
        raw = m.group(0)         # e.g. "[Charaka Samhita, Sutrasthana 1:41]"
        inner = m.group(1)
        parsed_list = extract_citations(raw)
        if not parsed_list:
            # Malformed; treat as invalid + strip
            invalid.append({"raw_text": raw, "reason": "unparseable"})
            invalid_raw_brackets.append(raw)
            continue
        parsed = parsed_list[0]
        if _citation_matches_retrieval(parsed, retrievals):
            valid.append(parsed)
        else:
            invalid.append({**parsed, "raw_text": raw, "reason": "not in retrieval set"})
            invalid_raw_brackets.append(raw)

    cleaned = text
    for raw in invalid_raw_brackets:
        cleaned = cleaned.replace(raw, "")
    # Tidy up artefacts from the stripped brackets
    cleaned = re.sub(r"\s+([.,;:])", r"\1", cleaned)   # space before punctuation
    cleaned = re.sub(r"\(\s*\)", "", cleaned)          # empty parens
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

    if invalid:
        logger.warning(
            "citation_validator: stripped %d hallucinated citations (%d valid)",
            len(invalid),
            len(valid),
        )
        for i in invalid:
            logger.info(
                "  HALLUCINATED CITATION: %s — reason=%s",
                i.get("raw_text", "?"),
                i.get("reason"),
            )

    # Dedupe valid citations by (source, chapter, verse)
    seen = set()
    deduped_valid = []
    for c in valid:
        key = (c.get("source"), c.get("chapter"), c.get("verse"))
        if key in seen:
            continue
        seen.add(key)
        deduped_valid.append(c)

    return ValidatedCitations(cleaned_text=cleaned, valid=deduped_valid, invalid=invalid)
