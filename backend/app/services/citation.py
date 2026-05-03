import re


def extract_citations(text: str) -> list[dict]:
    """Extract citation references from Claude's response text.

    Matches patterns like [Charaka Samhita, Sutra Sthana 1:42]
    """
    pattern = r'\[([^\]]+(?:Samhita|Hridaya|Sangraha|Nidana|Prakasha|Ratnavali|Ratna)[^\]]*)\]'
    matches = re.findall(pattern, text, re.IGNORECASE)

    citations = []
    seen = set()
    for match in matches:
        if match in seen:
            continue
        seen.add(match)

        parts = match.split(",")
        source = parts[0].strip()
        chapter = None
        verse = None

        if len(parts) > 1:
            rest = ",".join(parts[1:]).strip()
            verse_match = re.search(r'(\d+):(\d+)', rest)
            if verse_match:
                chapter = rest[:verse_match.start()].strip().rstrip(",").strip()
                verse = f"{verse_match.group(1)}:{verse_match.group(2)}"
            else:
                chapter = rest
        else:
            # No comma — citation might be `[Source X:Y]` or `[Source N.M]`.
            # Pull a trailing verse-like number off the source so we don't
            # leave it glued to the source name.
            verse_match = re.search(r'\s+(\d+[:.]\d+(?:[-]\d+(?:[.]\d+)?)?)\s*$', source)
            if verse_match:
                verse = verse_match.group(1)
                source = source[:verse_match.start()].strip()

        citations.append({
            "source": source,
            "chapter": chapter,
            "verse": verse,
            "text": f"[{match}]",
        })

    return citations


def format_citation_label(chunk_metadata: dict) -> str:
    """Format a citation label from chunk metadata for display."""
    source = chunk_metadata.get("source", "Unknown")
    chapter = chunk_metadata.get("chapter_name", chunk_metadata.get("chapter", ""))
    verse_start = chunk_metadata.get("verse_start", "")
    verse_end = chunk_metadata.get("verse_end", "")

    label = source
    if chapter:
        label += f", {chapter}"
    if verse_start:
        if verse_end and verse_end != verse_start:
            label += f" {verse_start}-{verse_end}"
        else:
            label += f" {verse_start}"
    return label
