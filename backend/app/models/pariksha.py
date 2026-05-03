"""Parīkṣā (examination) schema + decision-tree encoding.

Two models:

1. `ParikshaParam` — one row per canonical examination parameter from
   the classical schemas:

     - aṣṭa-vidha parīkṣā (8-fold, Yogaratnākara): nāḍī, mūtra, mala,
       jihvā, śabda, sparśa, dṛk, ākṛti.
     - daśa-vidha parīkṣā (10-fold, Caraka Vimāna 8.94): prakṛti, vikṛti,
       sāra, saṃhanana, pramāṇa, sātmya, sattva, āhāra-śakti,
       vyāyāma-śakti, vaya.
     - trividha parīkṣā (3-fold pramāṇas): pratyakṣa, anumāna, aupadeśika.
     - and a few sub-parameters carried by classical Caraka & Suśruta
       chapters (agni, koṣṭha, deśa, kāla, etc.).

   Each row carries `findings` — the list of canonical observable values
   for this parameter, with the doṣa/dhātu/agni implication of each
   value. This is what a Vaidya UI would offer as picklists.

2. `DiagnosticPattern` — a single rule "IF a clinically meaningful
   combination of findings is present, raise the diagnostic score for
   these vyādhi candidates by this weight." Patterns are
   text-grounded (each carries a classical_source) and review-tier-
   gated like everything else in the materia medica layer.

The two together let the chatbot present a structured aṣṭa-vidha + daśa-
vidha intake, then run a deterministic scoring pass that nominates the
top-K vyādhi candidates with citations — purely zero-LLM-cost.
"""
import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import GUID, JSONType


class ParikshaParam(Base):
    """One examination parameter from the classical parīkṣā schemas."""

    __tablename__ = "pariksha_params"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    # Identification
    name_iast: Mapped[str] = mapped_column(String(120), index=True)
    name_devanagari: Mapped[str | None] = mapped_column(String(120))
    english: Mapped[str | None] = mapped_column(String(200))
    hindi: Mapped[str | None] = mapped_column(String(200))

    # Classification
    schema_family: Mapped[str] = mapped_column(String(40), index=True)
    """aṣṭa-vidha | daśa-vidha | trividha | extra"""

    domain: Mapped[str | None] = mapped_column(String(40))
    """physical | physiological | mental | constitutional | other"""

    # Method
    examination_method: Mapped[str | None] = mapped_column(Text)
    """How a Vaidya elicits this parameter (palpation, observation, history)."""

    when_to_examine: Mapped[str | None] = mapped_column(String(200))
    """E.g. 'before sunrise on empty stomach' for nāḍī parīkṣā."""

    # Possible findings — the picklist
    findings: Mapped[list | None] = mapped_column(JSONType())
    """Canonical findings:
       [{value: 'vāta-nāḍī', description: '…', implies: {vata: '+', pitta: '0', kapha: '0'}}, …]
    Implication codes:
      '+'  raised (vṛddhi / prakopa)
      '0'  normal/sama
      '-'  diminished (kṣaya)
      '++' markedly raised (tīvra-prakopa)
      '--' markedly diminished
    """

    normal_finding: Mapped[str | None] = mapped_column(String(120))
    """The 'sama' / sustainable / healthy value, when defined."""

    # Provenance
    classical_source: Mapped[str | None] = mapped_column(String(200))
    classical_refs: Mapped[list | None] = mapped_column(JSONType())
    notes: Mapped[str | None] = mapped_column(Text)

    review_tier: Mapped[str] = mapped_column(String(20), default="llm-only")
    provenance: Mapped[dict | None] = mapped_column(JSONType())

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DiagnosticPattern(Base):
    """A weighted rule: combined findings → candidate vyādhi.

    A pattern fires when ALL of its `conditions` match the patient's
    reported findings. Score added to each `target` proportional to
    `weight`. Ranking is sum-of-weights across all matching patterns,
    not a probabilistic posterior — the scoring is intentionally
    interpretable (every score has named contributing rules).
    """

    __tablename__ = "diagnostic_patterns"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    # Pattern identity
    name: Mapped[str] = mapped_column(String(200), index=True)
    """Human-readable, e.g. 'Vāta-prakopa core pattern',
    'Madhumeha kapha-pradhāna', 'Āmavāta active flare'."""

    description: Mapped[str | None] = mapped_column(Text)

    pattern_type: Mapped[str] = mapped_column(String(40), default="vyadhi")
    """vyadhi | dosha-state | dhatu-state | agni-state | manas-state"""

    # Conditions — list of {param, finding, required: bool}
    conditions: Mapped[list] = mapped_column(JSONType())
    """List of {param: 'nadi', finding: 'vāta-nāḍī', required: true}.
    A pattern fires only when every required condition is present in
    the user's findings. Optional conditions raise the contribution
    weight when present but don't gate firing.
    """

    # Scoring targets
    targets: Mapped[list] = mapped_column(JSONType())
    """List of {target_kind: 'vyadhi' | 'dosha-state', name: 'Madhumeha',
    weight: 1.0, rationale: '…'}."""

    # Recommended response
    suggested_chikitsa: Mapped[list | None] = mapped_column(JSONType())
    """List of formulation/procedure names a Vaidya would consider
    when this pattern fires."""

    red_flags: Mapped[list | None] = mapped_column(JSONType())
    """Findings that, if present, demand immediate referral regardless
    of which target this rule normally promotes."""

    # Confidence
    evidence_grade: Mapped[str] = mapped_column(String(20), default="C")
    """A = textually + RCT-supported, B = single text + observational,
    C = single-text only, D = LLM-curated awaiting review."""

    # Provenance
    classical_source: Mapped[str | None] = mapped_column(String(200))
    classical_refs: Mapped[list | None] = mapped_column(JSONType())
    notes: Mapped[str | None] = mapped_column(Text)

    review_tier: Mapped[str] = mapped_column(String(20), default="llm-only")
    provenance: Mapped[dict | None] = mapped_column(JSONType())

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
