"""ModernEvidence — per-dravya scientific literature rows.

Each row links a Dravya (or future: Formulation, Vyādhi) to a single
peer-reviewed paper. Sourced from PubMed E-utilities (free, no API key
required for ≤3 req/s).

Schema follows govt/research-synthesis.md §6/§8:
  - Identifier: pmid (primary external key), doi, source_url.
  - Bibliographic: title, journal, year, authors[], pubtypes[], mesh_terms[].
  - Content: abstract_snippet (first ~500 chars), indication.
  - Quality grading: evidence_tier (A=SR/MA + classical concord, B=RCT,
    C=preclinical/observational, traditional-only=no modern data).
  - Foreign keys: dravya_id (others later).
  - Provenance: source_db = "pubmed" | "europepmc" | "ctri", fetched_at.

Idempotency: unique (pmid, dravya_id) — same paper can attach to multiple
dravyas (a study on Triphala touches Harītakī, Vibhītakī, Āmalakī — three
rows referencing the same PMID is correct).
"""
import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.types import GUID, JSONType


class ModernEvidence(Base):
    """One peer-reviewed paper attached to a Dravya."""

    __tablename__ = "modern_evidence"
    __table_args__ = (
        UniqueConstraint("pmid", "dravya_id", name="uq_pmid_dravya"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    pmid: Mapped[str] = mapped_column(String(40), index=True)
    doi: Mapped[str | None] = mapped_column(String(120))
    source_db: Mapped[str] = mapped_column(String(40), default="pubmed")
    source_url: Mapped[str | None] = mapped_column(String(400))

    # Bibliographic
    title: Mapped[str] = mapped_column(Text)
    journal: Mapped[str | None] = mapped_column(String(200))
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    authors: Mapped[list | None] = mapped_column(JSONType())
    """List of {last, first, initials} — first 6 then 'et al.'."""

    pubtypes: Mapped[list | None] = mapped_column(JSONType())
    """E.g. ['Randomized Controlled Trial', 'Systematic Review',
    'Meta-Analysis', 'Clinical Trial', 'Review', 'Case Reports']."""

    mesh_terms: Mapped[list | None] = mapped_column(JSONType())
    """MeSH descriptors — useful for indication / topic filtering."""

    # Content
    abstract_snippet: Mapped[str | None] = mapped_column(Text)
    indication: Mapped[str | None] = mapped_column(String(200))
    """Best-effort extracted indication (e.g. 'anxiety', 'osteoarthritis').
    Pulled from MeSH or abstract; unconfirmed without manual review."""

    # Quality grading
    evidence_tier: Mapped[str] = mapped_column(String(20), default="C")
    """A = SR/MA (≥1) with classical-text concordance
    B = ≥2 RCTs, well-designed
    C = preclinical / observational / single trial
    traditional-only = no modern data (placeholder marker, not stored here)
    """

    # Foreign keys
    dravya_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("dravyas.id"), index=True)

    # Provenance
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text)

    dravya: Mapped["Dravya"] = relationship()
