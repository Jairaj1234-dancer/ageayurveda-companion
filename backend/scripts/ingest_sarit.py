"""SARIT TEI → corpus_chunks ingestion pipeline.

Pulls the canonical SARIT TEI XML editions of the Bṛhattrayī (Caraka,
Suśruta, Aṣṭāṅga Hṛdaya) and ingests them as verse-level rows in the
existing corpus_chunks table.

Source: https://github.com/sarit/SARIT-corpus
License: CC-BY-SA 3.0 (attribution: SARIT, R.P. Das & R.E. Emmerick eds.)

For each verse:
  - text id parsed from xml:id (e.g. "Ah.1.1.001a" → text=Ah, sthana=1,
    chapter=1, verse=1, pada=a)
  - lines (a + c halves) concatenated to a single IAST stanza
  - IAST → Devanagari via vidyut.lipi
  - Chapter context prepended to the embedded text per the
    "contextual retrieval" pattern (Anthropic Contextual Retrieval)
  - Embedded with the configured sentence-transformers model
  - Stored with full provenance + license string

Usage:
    python -m scripts.ingest_sarit              # all 3 (slow first run)
    python -m scripts.ingest_sarit ah           # just Aṣṭāṅga Hṛdaya
    python -m scripts.ingest_sarit caraka       # just Caraka
    python -m scripts.ingest_sarit susruta      # just Suśruta

Re-running is safe: the script deletes existing rows for the source
before inserting, so corpus updates are idempotent.
"""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path
from typing import Iterable

import requests
from lxml import etree
from sqlalchemy import delete, func, select
from vidyut.lipi import Scheme, transliterate

from app.config import get_settings
from app.database import AsyncSessionLocal, Base, engine
from app.models import CorpusChunk  # noqa: F401 — registers model
from app.services.embedding import embed_many


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

# Each entry: (key, source_name, url, sthana_names_in_part_order)
SARIT_BASE = "https://raw.githubusercontent.com/sarit/SARIT-corpus/master"

SOURCES: dict[str, dict] = {
    "ah": {
        "source": "Aṣṭāṅga Hṛdaya",
        "url": f"{SARIT_BASE}/astangahrdayasamhita.xml",
        "sthana_names": [
            "Sūtrasthāna",
            "Śārīrasthāna",
            "Nidānasthāna",
            "Cikitsāsthāna",
            "Kalpasthāna",
            "Uttarasthāna",
        ],
        "id_prefix": "Ah",
    },
    "caraka": {
        "source": "Caraka Saṃhitā",
        "url": f"{SARIT_BASE}/carakasamhita.xml",
        "sthana_names": [
            "Sūtrasthāna",
            "Nidānasthāna",
            "Vimānasthāna",
            "Śārīrasthāna",
            "Indriyasthāna",
            "Cikitsāsthāna",
            "Kalpasthāna",
            "Siddhisthāna",
        ],
        "id_prefix": "CS",
    },
    "susruta": {
        "source": "Suśruta Saṃhitā",
        "url": f"{SARIT_BASE}/susrutasamhita.xml",
        "sthana_names": [
            "Sūtrasthāna",
            "Nidānasthāna",
            "Śārīrasthāna",
            "Cikitsāsthāna",
            "Kalpasthāna",
            "Uttaratantra",
        ],
        "id_prefix": "SS",
    },
}

LICENSE_LINE = "Sanskrit mūla: public domain · SARIT TEI: CC-BY-SA 3.0 (R.P. Das & R.E. Emmerick critical edition, conv. SARIT/Indica et Buddhica)"

NS = {
    "tei": "http://www.tei-c.org/ns/1.0",
    "xml": "http://www.w3.org/XML/1998/namespace",
}
XML_LANG = f"{{{NS['xml']}}}lang"
XML_ID = f"{{{NS['xml']}}}id"

CACHE_DIR = Path("/tmp")


# ---------------------------------------------------------------------------
# TEI parser
# ---------------------------------------------------------------------------

def _download_or_cache(url: str, key: str) -> Path:
    """Download SARIT TEI to /tmp once, reuse on re-run."""
    cache = CACHE_DIR / f"sarit_{key}.xml"
    if cache.exists() and cache.stat().st_size > 1_000_000:
        print(f"  using cached {cache} ({cache.stat().st_size:,} bytes)")
        return cache
    print(f"  downloading {url}")
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    cache.write_bytes(r.content)
    print(f"  cached {cache} ({cache.stat().st_size:,} bytes)")
    return cache


def _clean_text(text: str) -> str:
    """Strip the verse label, daṇḍa numbering, and excess whitespace."""
    if text is None:
        return ""
    # SARIT puts label as "Ah.1.1.001a " at start — already in <label>, but
    # strip just in case.
    text = re.sub(r"\s+", " ", text).strip()
    # Strip trailing daṇḍa+number ("|| 1 ||") for cleanliness; we capture
    # verse_num from the xml:id anyway.
    text = re.sub(r"\|\|\s*\d+\s*\|\|\s*$", "||", text).strip()
    return text


_SKIP_TAGS = {f"{{{NS['tei']}}}label", f"{{{NS['tei']}}}note"}


def _l_text(l_el) -> str:
    """Extract IAST text from an <l> element, ignoring <label> and <note>.

    Walk text + tail in document order, skipping subtrees we don't want.
    """
    parts: list[str] = []
    if l_el.text:
        parts.append(l_el.text)
    for child in l_el:
        if child.tag in _SKIP_TAGS:
            # Skip its body but still capture tail
            if child.tail:
                parts.append(child.tail)
            continue
        # Recurse into other children (variants, hi, etc.)
        sub = _l_text(child)
        if sub:
            parts.append(sub)
        if child.tail:
            parts.append(child.tail)
    return _clean_text(" ".join(p for p in parts if p))


_ID_RE = re.compile(r"^([A-Za-z]+)\.(\d+)\.(\d+)\.(\d+)([a-z]?)$")


def _parse_id(xml_id: str) -> tuple[str, int, int, int, str] | None:
    """Parse xml:id → (text, sthana, chapter, verse, pada)."""
    m = _ID_RE.match(xml_id or "")
    if not m:
        return None
    return m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), m.group(5)


def _heading_sanskrit(div) -> str | None:
    """Pick the Sanskrit head (no xml:lang) from a div's children."""
    for h in div.findall(f"{{{NS['tei']}}}head"):
        if not h.get(XML_LANG):
            txt = " ".join(h.itertext())
            return _clean_text(txt)
    return None


def parse_tei(path: Path, source_meta: dict) -> Iterable[dict]:
    """Yield verse dicts from a SARIT TEI file.

    Output shape:
      { source, section, chapter, chapter_name, verse_start, verse_end,
        sanskrit, transliteration }
    """
    tree = etree.parse(str(path))
    root = tree.getroot()

    # SARIT uses two conventions:
    #   AH       — type="part"   / type="chapter"
    #   Caraka,  — type="level1" / type="level2" (subtype="adhyāya")
    #    Suśruta
    # SARIT Suśruta has a literal typo "leve1" (missing 'l') in the source —
    # tolerate both spellings.
    PART_TYPES = {"part", "level1", "leve1"}
    CHAPTER_TYPES = {"chapter", "level2"}

    for part in root.iter(f"{{{NS['tei']}}}div"):
        if part.get("type") not in PART_TYPES:
            continue
        try:
            sthana_idx = int(part.get("n") or 0)
        except ValueError:
            sthana_idx = 0
        if not (1 <= sthana_idx <= len(source_meta["sthana_names"])):
            continue
        sthana_name = source_meta["sthana_names"][sthana_idx - 1]

        for chap in part.iter(f"{{{NS['tei']}}}div"):
            if chap.get("type") not in CHAPTER_TYPES:
                continue
            # Skip nested structures other than level2/chapter (Suśruta has
            # subtype="adhyāya" on level2 — keep it).
            try:
                ch_num = int(chap.get("n") or 0)
            except ValueError:
                ch_num = 0
            ch_name_iast = _heading_sanskrit(chap)
            ch_label = f"Ch.{ch_num}"
            if ch_name_iast:
                # Pull the first 4-5 words of the heading as the human-readable
                # chapter name; clean trailing classical particles.
                ch_short = ch_name_iast.split(" adhyāya")[0]
                ch_short = re.sub(r"^(Ath[āa]|Atha)\s*", "", ch_short)
                ch_short = re.sub(r"-?\s*adhyāyaḥ?\s*", "", ch_short)
                ch_short = re.sub(
                    r"(prathamaḥ|dvitīyaḥ|tṛtīyaḥ|caturthaḥ|pañcamaḥ|ṣaṣṭhaḥ|saptamaḥ"
                    r"|aṣṭamaḥ|navamaḥ|daśamaḥ|ekādaśaḥ|dvādaśaḥ|"
                    r"prathamaḥ|.*?ḥ)\s*$",
                    "",
                    ch_short,
                ).strip()
                ch_label = f"Ch.{ch_num} {ch_short}".strip()

            # SARIT uses two verse-unit conventions inside chapters:
            #   <lg>     = stanza (verse passages, e.g. AH, most of Caraka)
            #   <ab>     = anonymous block (prose passages, e.g. Suśruta
            #              Sūtra ch.1, parts of Caraka Vimāna)
            # Process both. Document-order iteration via .iter() preserves
            # the natural sequence so verse numbers are stable.
            for unit in chap.iter():
                tag = etree.QName(unit).localname
                if tag == "lg":
                    lines = unit.findall(f"{{{NS['tei']}}}l")
                    if not lines:
                        continue
                    stanza_iast = " / ".join(_l_text(l) for l in lines if _l_text(l)).strip()
                    verse_num = None
                    for l in lines:
                        pid = _parse_id(l.get(XML_ID) or "")
                        if pid:
                            verse_num = pid[3]
                            break
                    if verse_num is None:
                        # Try the lg's own xml:id
                        pid = _parse_id(unit.get(XML_ID) or "")
                        if pid:
                            verse_num = pid[3]
                elif tag == "ab":
                    stanza_iast = _l_text(unit)
                    pid = _parse_id(unit.get(XML_ID) or "")
                    verse_num = pid[3] if pid else None
                else:
                    continue

                if not stanza_iast or verse_num is None:
                    continue

                # Devanagari from IAST via vidyut
                try:
                    sanskrit_dev = transliterate(stanza_iast, Scheme.Iast, Scheme.Devanagari)
                except Exception:
                    sanskrit_dev = ""

                yield {
                    "source": source_meta["source"],
                    "section": sthana_name,
                    "chapter": ch_label,
                    "chapter_name": ch_short if ch_name_iast else None,
                    "verse_start": str(verse_num),
                    "verse_end": str(verse_num),
                    "sanskrit": sanskrit_dev,
                    "transliteration": stanza_iast,
                }


# ---------------------------------------------------------------------------
# Build embedding text — chapter-context prefix per Anthropic Contextual Retrieval
# ---------------------------------------------------------------------------

def _build_index_text(verse: dict) -> str:
    """Text passed to the sentence-transformer for indexing.

    Adds a short, deterministic chapter-context prefix so the embedding
    sees both source-context and verse content. This implements the
    "contextual retrieval" pattern (Anthropic, Sept 2024) at index time
    and gives a measurable retrieval lift on classical-text retrieval
    where the verse alone often lacks context.
    """
    prefix_parts = [verse["source"]]
    if verse.get("section"):
        prefix_parts.append(verse["section"])
    if verse.get("chapter"):
        prefix_parts.append(verse["chapter"])
    if verse.get("verse_start"):
        prefix_parts.append(f"v.{verse['verse_start']}")
    prefix = ", ".join(prefix_parts)

    body_parts = []
    if verse.get("transliteration"):
        body_parts.append(verse["transliteration"])
    if verse.get("sanskrit"):
        body_parts.append(verse["sanskrit"])

    return f"[{prefix}] " + " | ".join(body_parts)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def ensure_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def ingest_source(key: str, batch_size: int = 64) -> int:
    settings = get_settings()
    meta = SOURCES[key]
    print(f"\n=== {meta['source']} ===")
    path = _download_or_cache(meta["url"], key)

    print("  parsing TEI…")
    verses = list(parse_tei(path, meta))
    print(f"  parsed {len(verses):,} verses")
    if not verses:
        print("  nothing to ingest"); return 0

    # Sample sanity check
    sample = verses[0]
    print(f"  sample: [{sample['source']}, {sample['section']}, {sample['chapter']}, v.{sample['verse_start']}]")
    print(f"          IAST:  {sample['transliteration'][:100]}…")
    print(f"          Deva:  {sample['sanskrit'][:60]}…")

    # Embed in batches (sentence-transformers handles batching internally,
    # but we still chunk to bound memory).
    print(f"  embedding {len(verses):,} verses with {settings.embedding_model}…")
    texts = [_build_index_text(v) for v in verses]
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        embeddings.extend(embed_many(batch))
        if (i // batch_size) % 10 == 0:
            print(f"    embedded {min(i + batch_size, len(texts)):,}/{len(texts):,}")
    assert len(embeddings) == len(verses)

    # Bulk insert (replace existing rows for this source)
    async with AsyncSessionLocal() as db:
        await db.execute(delete(CorpusChunk).where(CorpusChunk.source == meta["source"]))
        await db.commit()

        chunks = []
        for v, emb in zip(verses, embeddings):
            chunks.append(
                CorpusChunk(
                    source=v["source"],
                    section=v["section"],
                    chapter=v["chapter"],
                    verse_start=v["verse_start"],
                    verse_end=v["verse_end"],
                    sanskrit=v["sanskrit"],
                    transliteration=v["transliteration"],
                    english=None,        # filled by separate enrichment script
                    summary=None,
                    license=LICENSE_LINE,
                    embedding=emb,
                    embedding_model=settings.embedding_model,
                    token_count=len(v["transliteration"].split()),
                )
            )

        # Batch the inserts to avoid SQLite parameter limits
        for i in range(0, len(chunks), 200):
            db.add_all(chunks[i : i + 200])
            await db.flush()
        await db.commit()

    return len(verses)


async def main(targets: list[str]) -> None:
    await ensure_tables()

    if not targets or targets == ["all"]:
        targets = list(SOURCES.keys())
    targets = [t for t in targets if t in SOURCES]
    if not targets:
        print(f"No valid sources. Pick from: {sorted(SOURCES)}")
        return

    total = 0
    for key in targets:
        total += await ingest_source(key)

    # Final summary
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CorpusChunk.source, func.count(CorpusChunk.id))
            .group_by(CorpusChunk.source)
            .order_by(CorpusChunk.source)
        )
        print(f"\nDone. Ingested {total:,} verses this run.")
        print("Corpus state:")
        for src, n in result.all():
            print(f"  {src}: {n:,}")


if __name__ == "__main__":
    args = [a.lower() for a in sys.argv[1:]]
    asyncio.run(main(args))
