"""Parīkṣā-finding → diagnostic candidate scoring.

Pure-function scoring engine. Inputs:
  - `findings` — list of {param, finding} dicts the user reported.
  - `patterns` — list of DiagnosticPattern rows.

Output:
  - `candidates` — list of {target_kind, name, score, rationale,
    contributing_patterns, suggested_chikitsa, red_flags}, ranked by
    score descending.

Scoring rule (deliberately interpretable, not probabilistic):
  - A pattern fires only when every condition with `required: true`
    is matched in the input findings.
  - When a pattern fires, each of its targets receives
    `pattern_weight × target_weight` added to its score.
  - Optional conditions that do match raise the multiplier by 1.2× per
    optional match (capped at 2× for pattern stability).
  - All matching pattern names + rationales are accumulated under each
    candidate so the final UI can show "why this was nominated."
  - Red-flags from any firing pattern are union-merged onto the
    matching candidates.

The scoring is intentionally additive and unnormalized — Vaidya UIs
compare relative scores, not absolute probabilities.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class Candidate:
    target_kind: str
    name: str
    score: float = 0.0
    rationale: list[str] = field(default_factory=list)
    contributing_patterns: list[str] = field(default_factory=list)
    suggested_chikitsa: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "target_kind": self.target_kind,
            "name": self.name,
            "score": round(self.score, 3),
            "rationale": self.rationale,
            "contributing_patterns": self.contributing_patterns,
            "suggested_chikitsa": list(dict.fromkeys(self.suggested_chikitsa)),
            "red_flags": list(dict.fromkeys(self.red_flags)),
        }


def _findings_to_set(findings: Iterable[dict]) -> set[tuple[str, str]]:
    """Normalize the input to a set of (param, finding) tuples for O(1) match."""
    return {
        (str(f.get("param", "")).strip(), str(f.get("finding", "")).strip())
        for f in findings
        if f.get("param") and f.get("finding")
    }


_OPTIONAL_BONUS = 1.2
_OPTIONAL_BONUS_CAP = 2.0


def _pattern_match(pattern_conditions: list[dict], finding_set: set) -> tuple[bool, int]:
    """Return (fires, n_optional_matched).
    Pattern fires when all required conditions are satisfied.
    """
    n_optional_match = 0
    for c in pattern_conditions or []:
        param = c.get("param", "").strip()
        finding = c.get("finding", "").strip()
        required = c.get("required", False)
        present = (param, finding) in finding_set
        if required and not present:
            return False, 0
        if not required and present:
            n_optional_match += 1
    return True, n_optional_match


def score_findings(
    findings: list[dict], patterns: list
) -> list[dict]:
    """Run all patterns against the given findings and return ranked
    candidates. `patterns` items can be ORM rows or dicts — both supported."""
    finding_set = _findings_to_set(findings)
    if not finding_set:
        return []

    candidates: dict[tuple[str, str], Candidate] = {}

    for pattern in patterns:
        # support both ORM row and plain dict
        get = (lambda k: getattr(pattern, k, None)) if not isinstance(pattern, dict) \
              else pattern.get
        conditions = get("conditions") or []
        targets = get("targets") or []
        name = get("name") or "(unnamed)"
        suggested = get("suggested_chikitsa") or []
        red_flags = get("red_flags") or []

        fires, n_opt = _pattern_match(conditions, finding_set)
        if not fires:
            continue

        bonus = min(_OPTIONAL_BONUS_CAP, _OPTIONAL_BONUS ** n_opt)

        for t in targets:
            kind = t.get("target_kind", "vyadhi")
            tname = t.get("name", "(unnamed)")
            tweight = float(t.get("weight", 1.0))
            rationale = t.get("rationale") or ""

            key = (kind, tname)
            cand = candidates.setdefault(key, Candidate(target_kind=kind, name=tname))
            cand.score += tweight * bonus
            cand.contributing_patterns.append(name)
            if rationale:
                cand.rationale.append(rationale)
            cand.suggested_chikitsa.extend(suggested)
            cand.red_flags.extend(red_flags)

    ranked = sorted(candidates.values(), key=lambda c: -c.score)
    return [c.to_dict() for c in ranked]
