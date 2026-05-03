"""Formulation (yoga / kalpa / aushadha) and FormulationIngredient models.

A Formulation is a classical Ayurvedic preparation — Triphala, Cyavanaprāśa,
Yogarāja Guggulu, Ashwagandhāriṣṭa, Mahānārāyaṇa Taila, etc. Composition is
modelled as a many-to-many relation to Dravya, with ingredient-level
metadata (proportion, role, processing).

Schema follows govt/research-synthesis.md §10:
  - Identification: name, classical refs, composition, kalpana type.
  - Therapeutic: primary indication(s), secondary, contra-indications.
  - Pharmaco: dose value/unit, anupāna, kāla, duration.
  - Quality: API/AFI monograph reference, manufacturing notes.
  - Safety: contraindications, drug interactions (free-text + structured),
    pregnancy/lactation status.
  - Provenance: source classical text + chapter + verse, review_tier.
"""
import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.types import GUID, JSONType


class Formulation(Base):
    """A classical Ayurvedic formulation."""

    __tablename__ = "formulations"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    # Identification
    name_iast: Mapped[str] = mapped_column(String(200), index=True)
    name_devanagari: Mapped[str | None] = mapped_column(String(200))
    english: Mapped[str | None] = mapped_column(String(200))
    hindi: Mapped[str | None] = mapped_column(String(200))

    kalpana_type: Mapped[str] = mapped_column(String(40), index=True)
    """One of: curṇa, vatī, guṭikā, avaleha, lehya, ghṛta, taila, āriṣṭa,
    āsava, kvātha, kalka, svarasa, hima, phāṇṭa, modaka, bhasma, parpaṭī,
    rasa-yoga, sneha, sandhāna, …"""

    # Therapeutic
    primary_indication: Mapped[str | None] = mapped_column(Text)
    indications: Mapped[list | None] = mapped_column(JSONType())
    """List of vyādhi this is classically prescribed for."""

    dosha_action: Mapped[dict | None] = mapped_column(JSONType())
    """{vata: śāmaka|vardhaka|sama, pitta: …, kapha: …}"""

    karma: Mapped[list | None] = mapped_column(JSONType())

    # Dose
    dose_value: Mapped[str | None] = mapped_column(String(80))
    dose_unit: Mapped[str | None] = mapped_column(String(40))
    anupana: Mapped[list | None] = mapped_column(JSONType())
    kala: Mapped[str | None] = mapped_column(String(120))
    duration: Mapped[str | None] = mapped_column(String(120))

    # Safety
    contraindications: Mapped[list | None] = mapped_column(JSONType())
    drug_interactions: Mapped[list | None] = mapped_column(JSONType())
    """List of {western_drug_class, severity: high|med|low, mechanism}"""

    pregnancy_lactation_status: Mapped[str | None] = mapped_column(String(60))
    pediatric_status: Mapped[str | None] = mapped_column(String(60))
    toxicity_notes: Mapped[str | None] = mapped_column(Text)

    # Quality / regulatory
    afi_ref: Mapped[str | None] = mapped_column(String(80))
    """Ayurvedic Formulary of India reference (e.g. AFI Vol I, Sec 1.1.1)"""

    api_ref: Mapped[str | None] = mapped_column(String(80))
    """API Part II reference"""

    ayush_stg_url: Mapped[str | None] = mapped_column(String(400))
    shelf_life_days: Mapped[int | None] = mapped_column(Integer)

    # Manufacturing
    method_summary: Mapped[str | None] = mapped_column(Text)

    # Classical reference
    classical_source: Mapped[str | None] = mapped_column(String(120))
    """E.g. 'Bhaiṣajya Ratnāvali Vātavyādhi-prakaraṇa', 'Sahasra Yoga'"""

    classical_chapter: Mapped[str | None] = mapped_column(String(120))
    classical_verse: Mapped[str | None] = mapped_column(String(80))

    # Provenance / audit
    notes: Mapped[str | None] = mapped_column(Text)
    review_tier: Mapped[str] = mapped_column(String(20), default="llm-only")
    provenance: Mapped[dict | None] = mapped_column(JSONType())

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    ingredients: Mapped[list["FormulationIngredient"]] = relationship(
        back_populates="formulation",
        cascade="all, delete-orphan",
        order_by="FormulationIngredient.position",
    )

    def display_name(self) -> str:
        return self.name_iast


class FormulationIngredient(Base):
    """One ingredient within a formulation, with quantity + role + processing."""

    __tablename__ = "formulation_ingredients"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    formulation_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("formulations.id"), index=True
    )
    dravya_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("dravyas.id"), index=True, nullable=True
    )
    """Resolved Dravya id when the ingredient matches a known dravya;
    nullable so we can ingest before all dravyas exist."""

    ingredient_name: Mapped[str] = mapped_column(String(200))
    """Free-text ingredient name (resolves to dravya_id where known)."""

    proportion: Mapped[str | None] = mapped_column(String(80))
    """E.g. '1 part', '500 g', '½ tola', '1:1:1'"""

    role: Mapped[str | None] = mapped_column(String(40))
    """pradhāna (primary), prakṣepa (additive), bhāvana, anupāna, śodhana"""

    processing: Mapped[str | None] = mapped_column(Text)
    """Free-text processing instruction (e.g. 'śuddha (purified with godugdha)')"""

    position: Mapped[int] = mapped_column(Integer, default=0)

    formulation: Mapped["Formulation"] = relationship(back_populates="ingredients")
    dravya: Mapped["Dravya | None"] = relationship()
