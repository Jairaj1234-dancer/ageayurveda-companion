"""Benchmark loader + types for the eval harness.

A benchmark is a YAML file under `app/data/eval/`. Each item is a question
plus its expected ground-truth verses (and optionally an `expected_refusal`
flag for safety items).

Schema:

    items:
      - id:                "ah_dincharya_abhyanga"
        question_en:       "What does Ayurveda recommend for daily practice?"
        question_hi:       "आयुर्वेद के अनुसार दिनचर्या क्या है?"
        expected_verses:   ["Aṣṭāṅga Hṛdaya|Sūtrasthāna|2.1", "...|2.7"]
        category:          "diagnostic|therapeutic|formulation|preventive|philosophical|safety"
        difficulty:        "easy|medium|hard"
        expected_refusal:  false   # true for items in the should-refuse subset
        notes:             "free-text"

Verse IDs are constructed as `source|section|verse_start` to match the
metric helpers in metrics.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "eval"


@dataclass
class BenchmarkItem:
    id: str
    question_en: str
    question_hi: str | None = None
    expected_verses: list[str] = field(default_factory=list)
    category: str = "general"
    difficulty: str = "medium"
    expected_refusal: bool = False
    notes: str | None = None


@dataclass
class Benchmark:
    name: str
    items: list[BenchmarkItem]

    @property
    def n_items(self) -> int:
        return len(self.items)

    def by_category(self) -> dict[str, list[BenchmarkItem]]:
        out: dict[str, list[BenchmarkItem]] = {}
        for item in self.items:
            out.setdefault(item.category, []).append(item)
        return out


def load_benchmark(path: Path | str) -> Benchmark:
    p = Path(path)
    if not p.exists():
        # Try resolving inside the data dir
        p = DATA_DIR / Path(path).name
    if not p.exists():
        raise FileNotFoundError(f"benchmark not found: {path}")

    with open(p) as f:
        doc = yaml.safe_load(f)

    items = [BenchmarkItem(**row) for row in doc.get("items", [])]
    return Benchmark(name=doc.get("name", p.stem), items=items)
