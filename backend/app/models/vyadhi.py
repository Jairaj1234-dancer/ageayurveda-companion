"""Vyādhi (disease/disorder) model with NAMASTE + ICD-11 TM2 mapping.

A Vyādhi is a classical Ayurvedic disease entity (e.g. Madhumeha, Sthaulya,
Hṛdroga, Āmavāta). The schema integrates two coding systems:

  - NAMASTE Ayurveda — Ministry of AYUSH's morbidity codebook
    (https://namstp.ayush.gov.in). ~4,500 vyādhi terms in hierarchical
    alpha-numeric codes. The canonical Indian-government vocabulary.

  - WHO ICD-11 TM2 — Traditional Medicine Module 2 of ICD-11
    (https://icd.who.int/browse11/l-m/en — chapter 26). Designed for
    dual-coding alongside ICD-11 main classification.

Schema follows govt/research-synthesis.md §11 + §5:
  - Identification: Sanskrit name + Devanagari + English + Hindi.
  - Codes: NAMASTE_code + ICD11_TM2_code + ICD11_main_code (allopathic
    correlate where one exists).
  - Doṣa typology (which doṣa-types are recognized — vāta-ja, pitta-ja,
    kapha-ja, sannipāta, āgantuja, etc.).
  - Pañca-nidāna slots: nidāna (causes), pūrvarūpa (prodrome), rūpa
    (signs), upaśaya (relieving factors), saṃprāpti (pathogenesis).
  - Sādhya-asādhya prognosis classification.
  - Classical references + AYUSH STG link.
"""
import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import GUID, JSONType


class Vyadhi(Base):
    """A classical Ayurvedic disease/disorder."""

    __tablename__ = "vyadhi"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    # Identification
    nama_sanskrit: Mapped[str] = mapped_column(String(160), index=True)
    nama_devanagari: Mapped[str | None] = mapped_column(String(160))
    english: Mapped[str | None] = mapped_column(String(200))
    hindi: Mapped[str | None] = mapped_column(String(200))
    synonyms: Mapped[list | None] = mapped_column(JSONType())

    # Coding systems
    namaste_code: Mapped[str | None] = mapped_column(String(60), index=True)
    """AYUSH NAMASTE Ayurveda code, e.g. 'AAA-1.2.3'."""

    icd11_tm2_code: Mapped[str | None] = mapped_column(String(40), index=True)
    """WHO ICD-11 Traditional Medicine Module 2, e.g. 'SK06.4'."""

    icd11_main_code: Mapped[str | None] = mapped_column(String(40))
    """Closest allopathic ICD-11 code if one exists. Used for hybrid
    diagnostic decision-trees."""

    # Classification
    chapter: Mapped[str | None] = mapped_column(String(120))
    """E.g. 'Mahāroga', 'Jvara', 'Atisāra', 'Kuṣṭha', 'Prameha', 'Vāta-vyādhi'."""

    dosha_typology: Mapped[list | None] = mapped_column(JSONType())
    """List of recognised type-variants per classical text:
    e.g. for jvara — ['vātaja', 'pittaja', 'kaphaja', 'vāta-pittaja',
    'vāta-kaphaja', 'pitta-kaphaja', 'sannipātaja', 'āgantuja']."""

    primary_dosha: Mapped[str | None] = mapped_column(String(40))
    """Predominant doṣa: vāta | pitta | kapha | sannipāta | tridoṣa."""

    primary_dushya: Mapped[list | None] = mapped_column(JSONType())
    """Tissues primarily involved (rasa, rakta, māṃsa, meda, asthi, majjā, śukra)."""

    srotas: Mapped[list | None] = mapped_column(JSONType())
    """Affected channels — annavaha, prāṇavaha, udakavaha, raktavaha,
    māṃsavaha, medovaha, asthivaha, majjāvaha, śukravaha, mūtravaha,
    purīṣavaha, svedavaha, ārtavavaha, stanyavaha, manovaha."""

    # Pañca-nidāna (Mādhava Nidāna methodology)
    nidana: Mapped[list | None] = mapped_column(JSONType())
    """Aetiological factors (causes)."""

    purva_rupa: Mapped[list | None] = mapped_column(JSONType())
    """Prodromal signs."""

    rupa: Mapped[list | None] = mapped_column(JSONType())
    """Manifest clinical signs."""

    upashaya: Mapped[list | None] = mapped_column(JSONType())
    """Diagnostic test by relief — what therapies/foods/regimens improve
    the condition (used to refine diagnosis when sign-set is ambiguous)."""

    samprapti_summary: Mapped[str | None] = mapped_column(Text)
    """Brief pathogenesis narrative."""

    # Prognosis
    sadhya_asadhya: Mapped[str | None] = mapped_column(String(40))
    """sukha-sādhya / kṛcchra-sādhya / yāpya / asādhya"""

    # Treatment outline
    chikitsa_summary: Mapped[str | None] = mapped_column(Text)
    """High-level therapeutic approach (śodhana / śamana / pathya-apathya)."""

    common_formulations: Mapped[list | None] = mapped_column(JSONType())
    """List of formulation name_iast strings classically prescribed."""

    common_dravyas: Mapped[list | None] = mapped_column(JSONType())
    """List of single-dravya names classically used."""

    # Modern integration
    modern_diagnostics: Mapped[list | None] = mapped_column(JSONType())
    """Modern lab/imaging adjuncts a Vaidya would order today
    (e.g. ['HbA1c', 'fasting glucose', 'lipid profile'] for madhumeha)."""

    red_flags_for_referral: Mapped[list | None] = mapped_column(JSONType())
    """Symptoms/signs that demand immediate allopathic referral."""

    # Classical references
    classical_refs: Mapped[list | None] = mapped_column(JSONType())
    """List of {text, chapter, verse} citations."""

    ayush_stg_url: Mapped[str | None] = mapped_column(String(400))

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
