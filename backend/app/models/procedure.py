"""Procedure (kriyā / karma) model — the protocol layer.

A Procedure is a structured clinical or daily-regimen protocol from
classical Ayurveda: pañcakarma, pūrva-karma, paścāt-karma, caryā,
rasāyana, vājīkaraṇa, and the regional bahirparimārjana therapies
(śirodhārā, pizhichil, navara-kizhi, etc.) catalogued in regional
classics and modern AYUSH STG documents.

Schema follows govt/research-synthesis.md §10 (procedures) and §12
(rasāyana). Distinct from Formulation: a Formulation is a substance
(curṇa, kvātha, ghṛta); a Procedure is an *action sequence* with
phased steps (pūrva-karma → pradhāna-karma → paścāt-karma).

Categories:
  - "panchakarma"      — vamana, virecana, basti, nasya, rakta-mokṣaṇa
  - "purva-karma"      — snehana, svedana
  - "paschat-karma"    — saṃsarjana-krama, peyādi-krama
  - "caryā"            — dinacaryā, ṛtucaryā, rātricaryā
  - "rasāyana"         — kuṭīpraveśika, vātātapika, ācāra-rasāyana, dravya-rasāyana
  - "vājīkaraṇa"       — male reproductive tonification
  - "kriyā-bāhya"      — external therapies: abhyaṅga, śirodhārā, pizhichil, …

Practitioner level:
  - "vaidya-only"   — needs BAMS or trained Pañcakarma technician
  - "supervised"    — can run under Vaidya supervision
  - "self-care"     — daily regimen anyone can adopt
"""
import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import GUID, JSONType


class Procedure(Base):
    """A classical Ayurvedic procedure / protocol."""

    __tablename__ = "procedures"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    # Identification
    name_iast: Mapped[str] = mapped_column(String(160), index=True)
    name_devanagari: Mapped[str | None] = mapped_column(String(160))
    english: Mapped[str | None] = mapped_column(String(200))
    hindi: Mapped[str | None] = mapped_column(String(200))
    synonyms: Mapped[list | None] = mapped_column(JSONType())

    # Classification
    category: Mapped[str] = mapped_column(String(40), index=True)
    """panchakarma | purva-karma | paschat-karma | caryā |
    rasāyana | vājīkaraṇa | kriyā-bāhya"""

    subcategory: Mapped[str | None] = mapped_column(String(80), index=True)
    """E.g. for caryā: 'dina' | 'ṛtu' | 'rātri'.
    For rasāyana: 'kuṭīpraveśika' | 'vātātapika' | 'ācāra' | 'dravya'.
    For basti: 'anuvāsana' | 'niruha' | 'mātrā' | 'kaṭi' | 'jānu' | 'hṛdaya'.
    For svedana: 'bāṣpa' | 'nāḍī' | 'piṇḍa' | 'ūṣma' | 'avagāha'."""

    practitioner_level: Mapped[str] = mapped_column(String(20), default="vaidya-only")
    """vaidya-only | supervised | self-care"""

    # Indications & contraindications
    primary_indication: Mapped[str | None] = mapped_column(Text)
    indications: Mapped[list | None] = mapped_column(JSONType())
    """List of vyādhi names or symptom strings."""

    dosha_action: Mapped[dict | None] = mapped_column(JSONType())
    """{vata: śāmaka|vardhaka|sama, pitta: …, kapha: …}"""

    contraindications: Mapped[list | None] = mapped_column(JSONType())
    """Both vyādhi (e.g. 'durbala', 'ati-kṣīṇa') and absolute states
    (e.g. 'pregnancy', 'recent fever', 'uncontrolled DM')."""

    # Phased protocol — most procedures have a 3-phase structure:
    # pūrva-karma (preparation) → pradhāna-karma (main) → paścāt-karma (post).
    purva_karma: Mapped[list | None] = mapped_column(JSONType())
    """List of preparation steps with dose/duration."""

    pradhana_karma: Mapped[list | None] = mapped_column(JSONType())
    """List of main-action steps."""

    paschat_karma: Mapped[list | None] = mapped_column(JSONType())
    """List of post-care steps (samsarjana-krama, abstinences, etc.)."""

    # Materials
    materials: Mapped[list | None] = mapped_column(JSONType())
    """Oils, herbs, equipment — list of {name, role, quantity}."""

    common_oils: Mapped[list | None] = mapped_column(JSONType())
    """Frequently-used taila names (Mahānārāyaṇa, Kṣīrabalā, Bhṛṅgarāja, …)."""

    common_dravyas: Mapped[list | None] = mapped_column(JSONType())
    """Frequently-used dravyas (e.g. for vamana: madanaphala, vacā, lavaṇa)."""

    # Timing / duration
    duration_days: Mapped[int | None] = mapped_column(Integer)
    """Typical course length in days, when fixed."""

    duration_notes: Mapped[str | None] = mapped_column(String(200))
    """E.g. 'until lakṣaṇa appear', '7-21 days', 'one month rasāyana'."""

    frequency: Mapped[str | None] = mapped_column(String(120))
    """E.g. 'daily', 'alternate days', 'one season per year'."""

    season: Mapped[list | None] = mapped_column(JSONType())
    """Recommended ṛtu(s): vasanta, grīṣma, varṣā, śarad, hemanta, śiśira."""

    time_of_day: Mapped[str | None] = mapped_column(String(80))
    """E.g. 'prātaḥ' (morning), 'sāyam' (evening), 'nityam' (any time)."""

    # Safety
    adverse_events: Mapped[list | None] = mapped_column(JSONType())
    """Known complications and their management (e.g. for vamana:
    ati-yoga → dehydration, mūrcchā → rest + sweet liquids)."""

    pregnancy_lactation_status: Mapped[str | None] = mapped_column(String(60))
    pediatric_status: Mapped[str | None] = mapped_column(String(60))
    geriatric_status: Mapped[str | None] = mapped_column(String(60))

    red_flags: Mapped[list | None] = mapped_column(JSONType())
    """Stop-and-refer signs."""

    # Modern integration
    modern_correlate: Mapped[str | None] = mapped_column(Text)
    """Brief note on closest modern analogue, when one exists."""

    spa_friendly_version: Mapped[str | None] = mapped_column(Text)
    """If a wellness-friendly variant exists (most śirodhārā etc. do)."""

    # References
    classical_source: Mapped[str | None] = mapped_column(String(120))
    """E.g. 'Caraka Saṃhitā Siddhi Sthāna 1', 'Suśruta Cikitsā 33'."""

    classical_refs: Mapped[list | None] = mapped_column(JSONType())
    """List of {text, chapter, verse} citations."""

    afi_ref: Mapped[str | None] = mapped_column(String(80))
    """Ayurvedic Formulary of India reference (vol/page)."""

    ayush_stg_url: Mapped[str | None] = mapped_column(String(400))
    """AYUSH Standard Treatment Guidelines link."""

    # Free-form
    description: Mapped[str | None] = mapped_column(Text)
    """Short narrative summary."""

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

    def display_name(self) -> str:
        if self.english and self.english != self.name_iast:
            return f"{self.name_iast} ({self.english})"
        return self.name_iast
