import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import GUID, JSONType


class CorpusChunk(Base):
    """A single retrievable unit of classical-text content.

    A chunk is one verse or a small group of related verses from a classical
    Ayurvedic text (Ashtanga Hridaya, Charaka Samhita, etc.). The embedding
    is stored as a JSON array — works on both SQLite (dev) and Postgres (prod)
    without pgvector. Phase-1 retrieval does cosine similarity in Python over
    the full corpus, which is fine for the seed corpus (low thousands of chunks).
    Swap to pgvector when the corpus grows past ~100K chunks.
    """

    __tablename__ = "corpus_chunks"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    source: Mapped[str] = mapped_column(String(120), index=True)
    section: Mapped[str | None] = mapped_column(String(120))
    chapter: Mapped[str | None] = mapped_column(String(120))
    verse_start: Mapped[str | None] = mapped_column(String(40))
    verse_end: Mapped[str | None] = mapped_column(String(40))

    sanskrit: Mapped[str | None] = mapped_column(Text)
    transliteration: Mapped[str | None] = mapped_column(Text)
    english: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)

    language: Mapped[str] = mapped_column(String(10), default="multi")
    license: Mapped[str | None] = mapped_column(String(120))
    embedding: Mapped[list] = mapped_column(JSONType())
    embedding_model: Mapped[str] = mapped_column(String(120))
    token_count: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def citation_label(self) -> str:
        parts = [self.source]
        if self.section:
            parts.append(self.section)
        if self.chapter:
            parts.append(self.chapter)
        if self.verse_start:
            v = self.verse_start
            if self.verse_end and self.verse_end != self.verse_start:
                v = f"{self.verse_start}-{self.verse_end}"
            parts.append(v)
        return ", ".join(parts)

    def grounding_text(self) -> str:
        """Text fed to the LLM as grounding context."""
        lines = [f"[{self.citation_label()}]"]
        if self.sanskrit:
            lines.append(f"Sanskrit: {self.sanskrit}")
        if self.transliteration:
            lines.append(f"Transliteration: {self.transliteration}")
        if self.english:
            lines.append(f"English: {self.english}")
        if self.summary:
            lines.append(f"Note: {self.summary}")
        return "\n".join(lines)
