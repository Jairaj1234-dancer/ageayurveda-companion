"""Wikidata SPARQL → Dravya enrichment.

For each Dravya with a Latin binomial, this script:
  1. Queries the Wikidata SPARQL endpoint for the taxon entity matching
     the binomial (handling taxon synonyms via P1420).
  2. Walks the parent-taxon chain (P171*) to find the family rank
     (P105 = wd:Q35409) and pulls the family's canonical name.
  3. Writes back: wikidata_qid, family (if Wikidata's value differs
     from the seed and we're in --apply-family-fix mode), and
     canonical_latin_binomial (if it differs).

Wikidata is permissively licensed (CC0). Rate limit ~1 req/s with a
descriptive User-Agent — that's the etiquette they ask for.

Idempotent: re-running only writes back when Wikidata has a value
the local row is missing or has set differently.

Usage:
    python -m scripts.enrich_wikidata                  # all dravyas with latin_binomial
    python -m scripts.enrich_wikidata --limit 5
    python -m scripts.enrich_wikidata --dravya Aśvagandhā
    python -m scripts.enrich_wikidata --dry-run        # query but don't write
    python -m scripts.enrich_wikidata --apply-family-fix
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from typing import Iterable

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, Base, engine
from app.models import Dravya  # noqa: F401 — registers all models


WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
USER_AGENT = (
    "AgeAyurvedaCompanion/0.1 "
    "(https://github.com/jairajsharma/ageayurveda-companion; dravya enrichment)"
)
_REQ_GAP = 1.0  # 1 req/s — Wikidata's politeness threshold
_last_req_at = 0.0


# ---- SPARQL -----------------------------------------------------------


def build_taxon_query(latin: str) -> str:
    """Match the Latin binomial against P225 on either the canonical taxon
    or any of its synonyms (P1420), then climb to family.

    P225 = taxon name
    P171 = parent taxon (transitive via *)
    P105 = taxonomic rank
    P1420 = taxon synonym (synonym → canonical)
    Q35409 = family (taxonomic rank)
    """
    # Escape double quotes — Latin binomials never contain them, but defensive.
    safe = latin.replace('"', '\\"')
    return (
        "SELECT ?taxon ?canonicalName ?familyName WHERE {\n"
        "  {\n"
        f'    ?taxon wdt:P225 "{safe}".\n'
        "  } UNION {\n"
        f'    ?syn wdt:P225 "{safe}".\n'
        "    ?syn wdt:P1420 ?taxon.\n"
        "  }\n"
        "  ?taxon wdt:P225 ?canonicalName.\n"
        "  OPTIONAL {\n"
        "    ?taxon wdt:P171* ?fam.\n"
        "    ?fam wdt:P105 wd:Q35409.\n"
        "    ?fam wdt:P225 ?familyName.\n"
        "  }\n"
        "} LIMIT 5"
    )


async def _throttled_post(client: httpx.AsyncClient, query: str) -> dict:
    """POST the SPARQL query. POST avoids URL-length issues on long queries
    and is the recommended form for non-trivial reads."""
    global _last_req_at
    now = time.monotonic()
    delta = now - _last_req_at
    if delta < _REQ_GAP:
        await asyncio.sleep(_REQ_GAP - delta)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/sparql-results+json",
    }
    r = await client.post(
        WIKIDATA_SPARQL_URL,
        data={"query": query},
        headers=headers,
        timeout=30.0,
    )
    _last_req_at = time.monotonic()
    r.raise_for_status()
    return r.json()


def _qid_from_uri(uri: str) -> str | None:
    """'http://www.wikidata.org/entity/Q282569' → 'Q282569'"""
    if not uri:
        return None
    return uri.rsplit("/", 1)[-1] if "wikidata.org/entity/" in uri else None


def parse_taxon_response(body: dict) -> dict | None:
    """Pick the highest-quality binding (one with familyName when available)."""
    rows = body.get("results", {}).get("bindings", [])
    if not rows:
        return None

    def with_family(b):
        return "familyName" in b

    best = next((b for b in rows if with_family(b)), rows[0])

    qid = _qid_from_uri(best.get("taxon", {}).get("value"))
    canonical = best.get("canonicalName", {}).get("value")
    family = best.get("familyName", {}).get("value")
    if not qid:
        return None
    return {
        "wikidata_qid": qid,
        "canonical_latin_binomial": canonical,
        "family": family,
    }


def candidate_binomials(latin: str) -> list[str]:
    """Yield Latin binomials to try, in priority order.

    The seed YAML sometimes encodes alternatives like
    'Eclipta alba / E. prostrata', 'Cinnamomum verum / C. zeylanicum',
    or qualifiers like 'Zingiber officinale (dried)' / 'Piper longum (root)'.
    Wikidata only indexes the canonical two-token binomial, so we strip
    parens, split on slashes, and expand abbreviated genera ('E. prostrata'
    → 'Eclipta prostrata' using the first-listed genus).
    """
    cands: list[str] = []
    seen: set[str] = set()

    def _push(c: str) -> None:
        c = c.strip()
        if c and c not in seen:
            seen.add(c)
            cands.append(c)

    # Original first.
    _push(latin)

    # Strip parenthesized qualifiers, e.g. "Foo bar (root)" → "Foo bar".
    no_parens = latin.split("(")[0].strip()
    if no_parens != latin:
        _push(no_parens)

    # Slash-split with abbreviation expansion.
    if "/" in no_parens:
        parts = [p.strip() for p in no_parens.split("/") if p.strip()]
        first_genus = parts[0].split()[0] if parts and parts[0].split() else None
        for p in parts:
            tokens = p.split()
            if not tokens:
                continue
            # Expand "E. prostrata" using the first-part genus.
            if (
                len(tokens) >= 2
                and tokens[0].endswith(".")
                and len(tokens[0]) <= 3
                and first_genus
            ):
                _push(f"{first_genus} {' '.join(tokens[1:])}")
            else:
                _push(p)

    # Final fallback: first two tokens of the original.
    tokens = no_parens.split()
    if len(tokens) >= 2:
        _push(f"{tokens[0]} {tokens[1]}")

    return cands


async def lookup_taxon(client: httpx.AsyncClient, latin: str) -> dict | None:
    """Try each candidate binomial in priority order; return on first hit."""
    for candidate in candidate_binomials(latin):
        body = await _throttled_post(client, build_taxon_query(candidate))
        parsed = parse_taxon_response(body)
        if parsed:
            return parsed
    return None


# ---- enrich -----------------------------------------------------------


def diff_dravya(dravya: Dravya, found: dict, apply_family_fix: bool) -> dict:
    """Compute the field updates to apply. Returns empty dict if no-op."""
    updates: dict = {}

    if found.get("wikidata_qid") and not dravya.wikidata_qid:
        updates["wikidata_qid"] = found["wikidata_qid"]
    elif found.get("wikidata_qid") and dravya.wikidata_qid != found["wikidata_qid"]:
        updates["wikidata_qid"] = found["wikidata_qid"]

    canonical = found.get("canonical_latin_binomial")
    if canonical and canonical != dravya.latin_binomial:
        # Only apply if local is empty — otherwise log as a divergence,
        # don't silently rewrite a hand-curated binomial.
        if not dravya.latin_binomial:
            updates["latin_binomial"] = canonical

    fam = found.get("family")
    if fam and not dravya.family:
        updates["family"] = fam
    elif fam and apply_family_fix and dravya.family != fam:
        updates["family"] = fam

    return updates


async def enrich_one(
    client: httpx.AsyncClient,
    db: AsyncSession,
    dravya: Dravya,
    apply_family_fix: bool,
    dry_run: bool,
) -> dict:
    out = {
        "status": "skipped",
        "found": False,
        "qid": None,
        "family_local": dravya.family,
        "family_wikidata": None,
        "family_match": None,
        "updates": {},
    }
    latin = (dravya.latin_binomial or "").strip()
    if not latin:
        return out

    try:
        found = await lookup_taxon(client, latin)
    except Exception as e:
        out["status"] = "error"
        out["error"] = str(e)
        return out

    if not found:
        out["status"] = "no_match"
        return out

    out["found"] = True
    out["qid"] = found.get("wikidata_qid")
    out["family_wikidata"] = found.get("family")
    if found.get("family") and dravya.family:
        out["family_match"] = found["family"].lower() == dravya.family.lower()

    updates = diff_dravya(dravya, found, apply_family_fix=apply_family_fix)
    out["updates"] = updates

    if not updates:
        out["status"] = "no_change"
        return out

    if dry_run:
        out["status"] = "dry_run"
        return out

    for k, v in updates.items():
        setattr(dravya, k, v)
    out["status"] = "updated"
    return out


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


async def main(args) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        dravyas = await _select_dravyas(db, only=args.dravya, limit=args.limit)

    if not dravyas:
        print("No dravyas to enrich.")
        return

    print(f"Enriching {len(dravyas)} dravyas from Wikidata SPARQL")
    print(f"  apply_family_fix={args.apply_family_fix}  dry_run={args.dry_run}")

    counts = {"updated": 0, "no_change": 0, "no_match": 0, "error": 0, "dry_run": 0,
              "skipped": 0}
    family_disagreements: list[dict] = []
    started = time.monotonic()

    async with httpx.AsyncClient() as client:
        async with AsyncSessionLocal() as db:
            # Re-fetch in this session so writes attach to it.
            dravyas = await _select_dravyas(db, only=args.dravya, limit=args.limit)
            for d in dravyas:
                report = await enrich_one(
                    client, db, d,
                    apply_family_fix=args.apply_family_fix,
                    dry_run=args.dry_run,
                )
                counts[report["status"]] = counts.get(report["status"], 0) + 1

                fam_match = report.get("family_match")
                if fam_match is False:
                    family_disagreements.append({
                        "nama_sanskrit": d.nama_sanskrit,
                        "latin": d.latin_binomial,
                        "local": report["family_local"],
                        "wikidata": report["family_wikidata"],
                    })

                badge = {
                    "updated": "✓",
                    "no_change": "·",
                    "no_match": "?",
                    "error": "!",
                    "dry_run": "→",
                    "skipped": "-",
                }.get(report["status"], "?")
                qid = report.get("qid") or "—"
                upd = ",".join(report["updates"].keys()) or "—"
                print(
                    f"  {badge} {d.nama_sanskrit:<18} {d.latin_binomial:<32} "
                    f"qid={qid:<10} updates={upd}"
                )

            if not args.dry_run:
                await db.commit()

    elapsed = time.monotonic() - started

    print(f"\nDone in {elapsed:.1f}s.")
    for k, v in counts.items():
        if v:
            print(f"  {k}: {v}")

    if family_disagreements:
        print(f"\nFamily disagreements ({len(family_disagreements)}) — "
              f"re-run with --apply-family-fix to overwrite local with Wikidata:")
        for d in family_disagreements:
            print(f"  {d['nama_sanskrit']:<18} ({d['latin']}): "
                  f"local={d['local']}  wikidata={d['wikidata']}")


def _parse_args(argv: Iterable[str] | None = None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dravya", type=str, default=None,
                   help="Process only the dravya whose nama_sanskrit matches exactly")
    p.add_argument("--dry-run", action="store_true",
                   help="Query Wikidata but don't write to DB")
    p.add_argument("--apply-family-fix", action="store_true",
                   help="When local family disagrees with Wikidata, overwrite local. "
                        "Default is to log the disagreement only.")
    return p.parse_args(argv)


if __name__ == "__main__":
    asyncio.run(main(_parse_args(sys.argv[1:])))
