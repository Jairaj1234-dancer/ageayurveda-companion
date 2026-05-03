"""Dravya (substance) and Phytochemical models — the materia medica layer.

Schema follows the dravyaguṇa-vijñāna conventions documented in the project's
research synthesis (govt/research-synthesis.md §9):

  - Identification: Sanskrit name, Devanagari, Latin binomial, family,
    Hindi, English, regional names.
  - Classification: varga (Bhāvaprakāśa primary), sthāvara/jaṅgama/pārthiva.
  - Pharmaco-properties: rasa (taste, multi), guṇa (qualities, multi),
    vīrya (potency), vipāka (post-digestive), prabhāva (specific action).
  - Doṣa-karma: vāta/pitta/kapha effect (śāmaka / vardhaka / sama).
  - Karma: list of classical actions (dīpana, pācana, anulomana, …).
  - Prayoga: list of indications.
  - Mātrā: dose value + unit + anupāna + kāla.
  - Safety: contraindications, viruddha, toxicity_notes,
    pregnancy_lactation_status.
  - Provenance: api_monograph_ref, nighantu_refs, source/page/reviewer,
    review_tier (vaidya|peer|llm-only).
  - Future: phytochemicals link, modern_pharmacology, clinical_evidence
    PMIDs (separate tables).

The schema is deliberately rich. Most rows will have many fields empty
at first ingestion — fields can be enriched incrementally via Vaidya
review, IMPPAT/CCRAS partnership, PubMed crawl etc.
"""
import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.types import GUID, JSONType


class Dravya(Base):
    """A single substance (plant, mineral, animal product) in the materia medica."""

    __tablename__ = "dravyas"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    # Identification
    nama_sanskrit: Mapped[str] = mapped_column(String(160), index=True)
    nama_devanagari: Mapped[str | None] = mapped_column(String(160))
    latin_binomial: Mapped[str | None] = mapped_column(String(200), index=True)
    family: Mapped[str | None] = mapped_column(String(120))
    english: Mapped[str | None] = mapped_column(String(200))
    hindi: Mapped[str | None] = mapped_column(String(200))
    regional_names: Mapped[list | None] = mapped_column(JSONType())

    # Classification
    dravya_type: Mapped[str] = mapped_column(String(40), default="sthāvara")
    """sthāvara (plant), jaṅgama (animal-derived), pārthiva (mineral),
    bhasma (calcined), kalpita (compounded). Default plant."""

    varga_bhavaprakasha: Mapped[str | None] = mapped_column(String(80), index=True)
    """E.g. Harītakyādi, Karpūrādi, Guḍūcyādi, Puṣpa, Vaṭādi, Āmrādi,
    Dhānya, Śimbidhānya, Śāka, Mūla-phalādi, …"""

    varga_other: Mapped[list | None] = mapped_column(JSONType())
    part_used: Mapped[list | None] = mapped_column(JSONType())

    # Pharmaco-properties (rasa-pañcaka)
    rasa: Mapped[list | None] = mapped_column(JSONType())
    """One or more of: madhura, amla, lavaṇa, kaṭu, tikta, kaṣāya"""

    guna: Mapped[list | None] = mapped_column(JSONType())
    """20 guṇas — gurū/laghu, śīta/uṣṇa, snigdha/rūkṣa, mṛdu/tīkṣṇa, …"""

    virya: Mapped[str | None] = mapped_column(String(20))
    """uṣṇa or śīta"""

    vipaka: Mapped[str | None] = mapped_column(String(20))
    """madhura, amla, kaṭu"""

    prabhava: Mapped[str | None] = mapped_column(Text)

    # Doṣa-karma
    dosha_karma: Mapped[dict | None] = mapped_column(JSONType())
    """{vata: śāmaka|vardhaka|sama, pitta: …, kapha: …}"""

    # Karma (actions)
    karma: Mapped[list | None] = mapped_column(JSONType())

    # Prayoga (indications)
    prayoga: Mapped[list | None] = mapped_column(JSONType())

    # Dose
    matra_value: Mapped[str | None] = mapped_column(String(80))
    matra_unit: Mapped[str | None] = mapped_column(String(40))
    anupana: Mapped[list | None] = mapped_column(JSONType())
    kala: Mapped[str | None] = mapped_column(String(120))

    # Safety
    contraindications: Mapped[list | None] = mapped_column(JSONType())
    viruddha: Mapped[list | None] = mapped_column(JSONType())
    toxicity_notes: Mapped[str | None] = mapped_column(Text)
    pregnancy_lactation_status: Mapped[str | None] = mapped_column(String(60))

    # Substitutes
    pratinidhi_dravya: Mapped[list | None] = mapped_column(JSONType())

    # External references
    api_monograph_ref: Mapped[str | None] = mapped_column(String(80))
    nighantu_refs: Mapped[list | None] = mapped_column(JSONType())
    imppat_id: Mapped[str | None] = mapped_column(String(40))
    wikidata_qid: Mapped[str | None] = mapped_column(String(40))
    pubchem_cid: Mapped[str | None] = mapped_column(String(40))

    # Free-form notes — pharmacology summary, classical anecdotes, etc.
    notes: Mapped[str | None] = mapped_column(Text)

    # Provenance / audit
    review_tier: Mapped[str] = mapped_column(String(20), default="llm-only")
    """vaidya | peer | llm-only — controls confidence display in UI."""

    provenance: Mapped[dict | None] = mapped_column(JSONType())

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    phytochemicals: Mapped[list["DravyaPhytochemical"]] = relationship(
        back_populates="dravya", cascade="all, delete-orphan"
    )

    def display_name(self) -> str:
        return self.nama_sanskrit + (f" ({self.latin_binomial})" if self.latin_binomial else "")


class Phytochemical(Base):
    """A single phytochemical compound — for the dravya↔molecule layer."""

    __tablename__ = "phytochemicals"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    name: Mapped[str] = mapped_column(String(200), index=True)
    iupac_name: Mapped[str | None] = mapped_column(String(400))
    chemical_class: Mapped[str | None] = mapped_column(String(120))
    inchikey: Mapped[str | None] = mapped_column(String(50), index=True)
    smiles: Mapped[str | None] = mapped_column(Text)
    molecular_formula: Mapped[str | None] = mapped_column(String(80))

    pubchem_cid: Mapped[str | None] = mapped_column(String(40), index=True)
    chembl_id: Mapped[str | None] = mapped_column(String(40))
    imppat_id: Mapped[str | None] = mapped_column(String(40))

    pharmacology_summary: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    dravyas: Mapped[list["DravyaPhytochemical"]] = relationship(
        back_populates="phytochemical", cascade="all, delete-orphan"
    )


class DravyaPhytochemical(Base):
    """Many-to-many link between dravya and phytochemical, with provenance."""

    __tablename__ = "dravya_phytochemicals"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    dravya_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("dravyas.id"), index=True)
    phytochemical_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("phytochemicals.id"), index=True)

    plant_part: Mapped[str | None] = mapped_column(String(80))
    """Where in the plant the compound is found (root, leaf, fruit, …)"""

    abundance_class: Mapped[str | None] = mapped_column(String(40))
    """High / medium / low / trace — qualitative."""

    source_ref: Mapped[str | None] = mapped_column(String(120))
    """E.g. 'IMPPAT 2.0', 'PubChem assay xyz', 'PMID 12345678'."""

    dravya: Mapped["Dravya"] = relationship(back_populates="phytochemicals")
    phytochemical: Mapped["Phytochemical"] = relationship(back_populates="dravyas")
