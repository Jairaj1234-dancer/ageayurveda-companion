"""PubMed E-utilities → modern_evidence ingestion.

For each Dravya with a Latin binomial, this script:
  1. Calls esearch.fcgi to find PMIDs matching the Latin binomial
     in title/abstract.
  2. Calls efetch.fcgi to fetch full PubMed records as XML.
  3. Parses each record into a ModernEvidence row.
  4. Tiers each row by pubtype (A = SR/MA, B = RCT, C = other).
  5. Upserts by (pmid, dravya_id) — same paper can attach to multiple
     dravyas (one Triphala study touches three rows).

Rate-limited to 3 req/s — the unauthenticated NCBI ceiling. With an
NCBI_API_KEY env var the limit lifts to 10 req/s.

Usage:
    python -m scripts.ingest_pubmed                  # all dravyas with latin_binomial
    python -m scripts.ingest_pubmed --limit 5        # first 5 dravyas only
    python -m scripts.ingest_pubmed --dravya Aśvagandhā
    python -m scripts.ingest_pubmed --max-results 50 # PMIDs per dravya (default 30)
    python -m scripts.ingest_pubmed --dry-run        # parse but don't write
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Iterable

import httpx
from lxml import etree
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, Base, engine
from app.models import Dravya, ModernEvidence  # noqa: F401 — registers all models


EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DEFAULT_RETMAX = 30
EFETCH_BATCH = 200  # NCBI tolerates up to ~200 PMIDs per efetch call

# Rate-limit gap between requests.
# 3 req/s without API key, 10 req/s with one.
NCBI_API_KEY = os.getenv("NCBI_API_KEY") or None
_REQ_GAP = 0.34 if not NCBI_API_KEY else 0.11
_last_req_at = 0.0


# ---- evidence tiering -------------------------------------------------

# Pubtype strings as PubMed emits them.
TIER_A_PUBTYPES = {
    "Systematic Review",
    "Meta-Analysis",
    "Network Meta-Analysis",
}
TIER_B_PUBTYPES = {
    "Randomized Controlled Trial",
    "Pragmatic Clinical Trial",
    "Equivalence Trial",
}
TIER_C_PUBTYPES = {
    "Clinical Trial",
    "Clinical Trial, Phase I",
    "Clinical Trial, Phase II",
    "Clinical Trial, Phase III",
    "Clinical Trial, Phase IV",
    "Controlled Clinical Trial",
    "Observational Study",
    "Multicenter Study",
    "Case Reports",
    "Comparative Study",
    "Validation Study",
    "Review",
}


def tier_for_pubtypes(pubtypes: list[str]) -> str:
    """Map a paper's pubtypes to A/B/C/D.

    A = SR/MA — the strongest.
    B = RCT (any single RCT promotes to B).
    C = other clinical / observational / preclinical-with-design.
    D = no clinical evidence (review, news, comment, editorial only).

    Note: "≥2 RCTs" tier B at the *dravya* level is computed during
    the rollup phase by aggregating per-PMID rows, not here.
    """
    s = set(pubtypes)
    if s & TIER_A_PUBTYPES:
        return "A"
    if s & TIER_B_PUBTYPES:
        return "B"
    if s & TIER_C_PUBTYPES:
        return "C"
    return "D"


# ---- HTTP layer (rate-limited) ----------------------------------------


async def _throttled_get(client: httpx.AsyncClient, url: str, params: dict) -> httpx.Response:
    """Throttle calls to NCBI's E-utilities endpoint."""
    global _last_req_at
    now = time.monotonic()
    delta = now - _last_req_at
    if delta < _REQ_GAP:
        await asyncio.sleep(_REQ_GAP - delta)
    if NCBI_API_KEY:
        params = {**params, "api_key": NCBI_API_KEY}
    r = await client.get(url, params=params, timeout=30.0)
    _last_req_at = time.monotonic()
    r.raise_for_status()
    return r


# ---- esearch + efetch -------------------------------------------------


def _build_query(latin: str, clinical_only: bool) -> str:
    """Search for the Latin binomial in title/abstract.

    Default mode (clinical_only=True) restricts to human studies AND a
    high-quality publication type — RCT, SR/MA, clinical trial, or review.
    Without this filter the most-recent default sort is dominated by
    in-silico, preclinical and phytotoxicity papers (tier D), which buries
    real clinical evidence. This filter mirrors what a Vaidya searching
    PubMed would type.
    """
    base = f'"{latin}"[Title/Abstract] AND english[Language]'
    if not clinical_only:
        return base
    pubtype_filter = (
        "("
        "Randomized Controlled Trial[ptyp] OR "
        "Systematic Review[ptyp] OR "
        "Meta-Analysis[ptyp] OR "
        "Clinical Trial[ptyp] OR "
        "Review[ptyp]"
        ")"
    )
    return f"{base} AND humans[Filter] AND {pubtype_filter}"


async def esearch(
    client: httpx.AsyncClient, query: str, retmax: int, sort: str = "relevance"
) -> list[str]:
    r = await _throttled_get(
        client,
        f"{EUTILS_BASE}/esearch.fcgi",
        params={
            "db": "pubmed", "term": query, "retmax": retmax,
            "retmode": "json", "sort": sort,
        },
    )
    body = r.json()
    return body.get("esearchresult", {}).get("idlist", [])


async def efetch(client: httpx.AsyncClient, pmids: list[str]) -> bytes:
    r = await _throttled_get(
        client,
        f"{EUTILS_BASE}/efetch.fcgi",
        params={"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"},
    )
    return r.content


# ---- XML parsing ------------------------------------------------------


def _text(el) -> str | None:
    if el is None:
        return None
    return "".join(el.itertext()).strip() or None


def _first(parent, xpath: str):
    """Return the first matching element or None."""
    found = parent.find(xpath)
    return found


def _author_dict(a) -> dict | None:
    last = _text(_first(a, "LastName"))
    first = _text(_first(a, "ForeName")) or _text(_first(a, "FirstName"))
    initials = _text(_first(a, "Initials"))
    collective = _text(_first(a, "CollectiveName"))
    if collective and not last:
        return {"collective": collective}
    if not last:
        return None
    return {"last": last, "first": first, "initials": initials}


def _abstract_snippet(article_el) -> str | None:
    parts = []
    for txt in article_el.findall(".//Abstract/AbstractText"):
        label = txt.get("Label")
        body = "".join(txt.itertext()).strip()
        if not body:
            continue
        parts.append(f"{label}: {body}" if label else body)
    full = " ".join(parts).strip()
    if not full:
        return None
    return full[:500]


def _doi(pubmed_data_el) -> str | None:
    if pubmed_data_el is None:
        return None
    for art_id in pubmed_data_el.findall(".//ArticleId"):
        if art_id.get("IdType") == "doi":
            return _text(art_id)
    return None


def _year(article_el) -> int | None:
    for path in (".//PubDate/Year", ".//ArticleDate/Year", ".//PubDate/MedlineDate"):
        el = article_el.find(path)
        if el is None:
            continue
        text = _text(el)
        if not text:
            continue
        # "MedlineDate" is sometimes "2018 Jan-Feb" — grab leading 4 digits.
        digits = "".join(c for c in text[:4] if c.isdigit())
        if len(digits) == 4:
            try:
                return int(digits)
            except ValueError:
                pass
    return None


def parse_pubmed_article(article_root) -> dict | None:
    """Parse one <PubmedArticle> element into a dict ready for upsert."""
    medline = _first(article_root, "MedlineCitation")
    if medline is None:
        return None
    pmid_el = _first(medline, "PMID")
    pmid = _text(pmid_el)
    if not pmid:
        return None

    article = _first(medline, "Article")
    if article is None:
        return None

    title = _text(_first(article, "ArticleTitle"))
    journal = _text(_first(article, "Journal/Title")) or _text(
        _first(article, "Journal/ISOAbbreviation")
    )
    year = _year(article)

    authors = []
    for a in article.findall(".//AuthorList/Author"):
        d = _author_dict(a)
        if d:
            authors.append(d)
    # First 6 authors then 'et al.' is a render-time concern; store all here.

    pubtypes = [
        _text(p)
        for p in article.findall(".//PublicationTypeList/PublicationType")
        if _text(p)
    ]

    mesh_terms = []
    for mh in medline.findall(".//MeshHeadingList/MeshHeading/DescriptorName"):
        t = _text(mh)
        if t:
            mesh_terms.append(t)

    abstract_snippet = _abstract_snippet(article)

    pubmed_data = _first(article_root, "PubmedData")
    doi = _doi(pubmed_data)

    return {
        "pmid": pmid,
        "doi": doi,
        "source_db": "pubmed",
        "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "title": title or "[no title]",
        "journal": journal,
        "year": year,
        "authors": authors or None,
        "pubtypes": pubtypes or None,
        "mesh_terms": mesh_terms or None,
        "abstract_snippet": abstract_snippet,
        "evidence_tier": tier_for_pubtypes(pubtypes),
    }


def parse_efetch_xml(xml_bytes: bytes) -> list[dict]:
    """Parse an efetch response (zero or more <PubmedArticle> entries)."""
    if not xml_bytes:
        return []
    root = etree.fromstring(xml_bytes)
    out = []
    for art in root.findall(".//PubmedArticle"):
        parsed = parse_pubmed_article(art)
        if parsed:
            out.append(parsed)
    return out


# ---- upsert -----------------------------------------------------------


async def upsert_evidence(
    db: AsyncSession, parsed: dict, dravya_id, indication_hint: str | None
) -> str:
    """Idempotent upsert by (pmid, dravya_id). Returns 'inserted' or 'updated'."""
    pmid = parsed["pmid"]
    stmt = select(ModernEvidence).where(
        ModernEvidence.pmid == pmid, ModernEvidence.dravya_id == dravya_id
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    payload = {
        **parsed,
        "dravya_id": dravya_id,
        "indication": indication_hint,
    }

    if existing:
        for k, v in payload.items():
            setattr(existing, k, v)
        return "updated"

    db.add(ModernEvidence(**payload))
    return "inserted"


# ---- driver -----------------------------------------------------------


async def _select_dravyas(
    db: AsyncSession, only: str | None, limit: int | None
) -> list[Dravya]:
    stmt = select(Dravya).where(Dravya.latin_binomial.is_not(None))
    if only:
        stmt = stmt.where(Dravya.nama_sanskrit == only)
    stmt = stmt.order_by(Dravya.nama_sanskrit)
    rows = (await db.execute(stmt)).scalars().all()
    if limit:
        rows = rows[:limit]
    return rows


async def ingest_for_dravya(
    client: httpx.AsyncClient,
    db: AsyncSession,
    dravya: Dravya,
    retmax: int,
    dry_run: bool,
    clinical_only: bool = True,
) -> dict:
    """Search PubMed for one dravya and ingest results."""
    counters = {"found": 0, "parsed": 0, "inserted": 0, "updated": 0, "errors": 0}

    latin = dravya.latin_binomial.strip() if dravya.latin_binomial else None
    if not latin:
        return counters

    try:
        pmids = await esearch(
            client, _build_query(latin, clinical_only=clinical_only), retmax=retmax
        )
    except Exception as e:
        print(f"  esearch failed for {dravya.nama_sanskrit} ({latin}): {e}")
        counters["errors"] += 1
        return counters

    counters["found"] = len(pmids)
    if not pmids:
        return counters

    indication_hint = None  # could pull from Dravya.prayoga later if useful

    for i in range(0, len(pmids), EFETCH_BATCH):
        batch = pmids[i : i + EFETCH_BATCH]
        try:
            xml_bytes = await efetch(client, batch)
        except Exception as e:
            print(f"  efetch failed for {dravya.nama_sanskrit} batch {i}: {e}")
            counters["errors"] += 1
            continue

        parsed_rows = parse_efetch_xml(xml_bytes)
        counters["parsed"] += len(parsed_rows)

        if dry_run:
            continue

        for parsed in parsed_rows:
            outcome = await upsert_evidence(db, parsed, dravya.id, indication_hint)
            counters[outcome] += 1

    if not dry_run:
        await db.commit()

    return counters


async def main(args) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        dravyas = await _select_dravyas(db, only=args.dravya, limit=args.limit)

    if not dravyas:
        print("No dravyas to process. Are seed_top30 dravyas ingested?")
        return

    print(f"Ingesting PubMed evidence for {len(dravyas)} dravyas")
    print(f"  retmax/dravya={args.max_results}  dry_run={args.dry_run}")
    print(f"  clinical_only={not args.include_preclinical}")
    print(f"  ncbi_api_key={'set' if NCBI_API_KEY else 'unset (3 req/s)'}")

    grand = {"found": 0, "parsed": 0, "inserted": 0, "updated": 0, "errors": 0}
    started = time.monotonic()

    async with httpx.AsyncClient() as client:
        async with AsyncSessionLocal() as db:
            for d in dravyas:
                print(f"\n→ {d.nama_sanskrit} ({d.latin_binomial})")
                c = await ingest_for_dravya(
                    client, db, d,
                    retmax=args.max_results,
                    dry_run=args.dry_run,
                    clinical_only=not args.include_preclinical,
                )
                for k, v in c.items():
                    grand[k] += v
                print(
                    f"  found={c['found']} parsed={c['parsed']} "
                    f"inserted={c['inserted']} updated={c['updated']} errors={c['errors']}"
                )

    elapsed = time.monotonic() - started

    async with AsyncSessionLocal() as db:
        from sqlalchemy import func as f
        total_rows = (await db.execute(select(f.count(ModernEvidence.id)))).scalar_one()

    print(
        f"\nDone in {elapsed:.1f}s. "
        f"found={grand['found']} parsed={grand['parsed']} "
        f"inserted={grand['inserted']} updated={grand['updated']} "
        f"errors={grand['errors']}"
    )
    print(f"modern_evidence now has {total_rows} rows")


def _parse_args(argv: Iterable[str] | None = None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--max-results", type=int, default=DEFAULT_RETMAX,
                   help=f"PMIDs to fetch per dravya (default {DEFAULT_RETMAX})")
    p.add_argument("--limit", type=int, default=None,
                   help="Process only the first N dravyas (debug)")
    p.add_argument("--dravya", type=str, default=None,
                   help="Process only the dravya whose nama_sanskrit matches exactly")
    p.add_argument("--dry-run", action="store_true",
                   help="Parse but don't write to DB")
    p.add_argument("--include-preclinical", action="store_true",
                   help="Drop the human-studies + clinical-pubtype filter "
                        "(default keeps only RCT/SR/MA/CT/Review on humans)")
    return p.parse_args(argv)


if __name__ == "__main__":
    asyncio.run(main(_parse_args(sys.argv[1:])))
