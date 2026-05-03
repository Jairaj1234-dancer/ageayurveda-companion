"""KnowledgeEdge — typed (source, predicate, target) triples across the
materia-medica + diagnostic models.

A materialized graph layer derived from the existing tables. Build script
walks all source models and emits an edge per cross-reference (e.g.
Procedure.common_dravyas[i] → KnowledgeEdge(predicate='uses')).

Why a materialized table instead of computing on the fly: the cross-refs
are name-strings on JSON columns, so 'show me everything connected to
Madhumeha' would otherwise require multi-table SUBSTR/JSON-search per
request. A nightly (or after-ingest) rebuild keeps queries cheap and
keeps name→UUID resolution centralized.

Edge predicates (intentionally finite, classical-aligned):
  - 'ingredient_of'       Dravya → Formulation
  - 'indicated_for'       Dravya/Formulation/Procedure → Vyādhi
  - 'uses'                Procedure → Dravya/Formulation
  - 'diagnoses'           DiagnosticPattern → Vyādhi/dosha-state
  - 'suggests_chikitsa'   DiagnosticPattern → Procedure/Formulation/Dravya
  - 'used_in'             ParikshaParam → DiagnosticPattern
  - 'has_evidence'        Dravya → ModernEvidence
"""
import uuid
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, Float, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import GUID, JSONType


class KnowledgeEdge(Base):
    """One directed, typed edge between two entities in the KG."""

    __tablename__ = "knowledge_edges"
    __table_args__ = (
        Index("ix_kg_source", "source_kind", "source_id"),
        Index("ix_kg_target", "target_kind", "target_id"),
        Index("ix_kg_target_name", "target_kind", "target_name"),
        Index("ix_kg_predicate", "predicate"),
        UniqueConstraint(
            "source_kind", "source_id", "predicate",
            "target_kind", "target_id", "target_name",
            name="uq_kg_edge_signature",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    predicate: Mapped[str] = mapped_column(String(40))
    """ingredient_of | indicated_for | uses | diagnoses |
    suggests_chikitsa | used_in | has_evidence"""

    source_kind: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    source_name: Mapped[str] = mapped_column(String(240))

    target_kind: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    target_name: Mapped[str] = mapped_column(String(240))
    """target_name is always set even when target_id resolved.
    When target_id is NULL, the cross-reference exists in source data
    but no entity row matched it (likely a dravya/formulation outside
    the seeded set)."""

    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    """1.0 = direct FK or exact name match;
    0.7 = case/diacritic fuzzy match;
    0.5 = name-only, no entity row resolved."""

    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    """Source-specific weight if applicable (e.g. DiagnosticPattern target weight)."""

    provenance: Mapped[dict | None] = mapped_column(JSONType())
    """Which model field the edge was derived from, e.g.
    {model: 'Procedure', field: 'common_dravyas', position: 2}."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<KnowledgeEdge {self.source_kind}:{self.source_name} "
            f"--{self.predicate}--> {self.target_kind}:{self.target_name}>"
        )
