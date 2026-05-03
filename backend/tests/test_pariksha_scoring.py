"""Parīkṣā scoring service — pure logic tests."""
import pytest

from app.services.pariksha_scoring import score_findings, _findings_to_set, _pattern_match


# ---- helpers ---------------------------------------------------------


def _vata_pattern():
    return {
        "name": "Vāta-prakopa",
        "pattern_type": "dosha-state",
        "conditions": [
            {"param": "Nāḍī", "finding": "vāta-nāḍī", "required": True},
            {"param": "Sparśa", "finding": "śīta-rūkṣa-khara", "required": False},
            {"param": "Mala", "finding": "vibandha-rūkṣa", "required": False},
        ],
        "targets": [
            {"target_kind": "dosha-state", "name": "vāta-vṛddhi", "weight": 1.0,
             "rationale": "Nāḍī is decisive."},
        ],
        "suggested_chikitsa": ["Anuvāsana Basti"],
        "red_flags": [],
    }


def _madhumeha_pattern():
    return {
        "name": "Madhumeha kapha",
        "pattern_type": "vyadhi",
        "conditions": [
            {"param": "Mūtra", "finding": "madhura-mūtra", "required": True},
        ],
        "targets": [
            {"target_kind": "vyadhi", "name": "Madhumeha", "weight": 1.0},
        ],
        "suggested_chikitsa": ["Niruha Basti"],
        "red_flags": ["DKA — refer"],
    }


# ---- _pattern_match --------------------------------------------------


def test_required_condition_must_match_for_pattern_to_fire():
    finding_set = {("Sparśa", "śīta-rūkṣa-khara")}  # required missing
    fires, _ = _pattern_match(_vata_pattern()["conditions"], finding_set)
    assert fires is False


def test_pattern_fires_with_only_required_match():
    finding_set = {("Nāḍī", "vāta-nāḍī")}
    fires, n_opt = _pattern_match(_vata_pattern()["conditions"], finding_set)
    assert fires is True
    assert n_opt == 0


def test_optional_matches_increment_bonus_count():
    finding_set = {
        ("Nāḍī", "vāta-nāḍī"),
        ("Sparśa", "śīta-rūkṣa-khara"),
        ("Mala", "vibandha-rūkṣa"),
    }
    fires, n_opt = _pattern_match(_vata_pattern()["conditions"], finding_set)
    assert fires is True
    assert n_opt == 2


# ---- score_findings --------------------------------------------------


def test_empty_findings_yields_no_candidates():
    assert score_findings([], [_vata_pattern()]) == []


def test_single_pattern_fires_and_returns_candidate():
    findings = [{"param": "Nāḍī", "finding": "vāta-nāḍī"}]
    out = score_findings(findings, [_vata_pattern()])
    assert len(out) == 1
    cand = out[0]
    assert cand["name"] == "vāta-vṛddhi"
    assert cand["target_kind"] == "dosha-state"
    assert cand["score"] == 1.0
    assert "Vāta-prakopa" in cand["contributing_patterns"]
    assert "Anuvāsana Basti" in cand["suggested_chikitsa"]


def test_optional_findings_apply_bonus_multiplier():
    """Each optional match gives a 1.2× bonus capped at 2×."""
    findings = [
        {"param": "Nāḍī", "finding": "vāta-nāḍī"},
        {"param": "Sparśa", "finding": "śīta-rūkṣa-khara"},
    ]
    out = score_findings(findings, [_vata_pattern()])
    assert out[0]["score"] == pytest.approx(1.2, rel=1e-3)


def test_optional_bonus_is_capped_at_2x():
    """Even with many optional matches, bonus does not exceed 2×."""
    huge_pattern = {
        "name": "huge",
        "pattern_type": "vyadhi",
        "conditions": [{"param": "P", "finding": "f-required", "required": True}]
        + [{"param": f"P{i}", "finding": f"f{i}", "required": False} for i in range(10)],
        "targets": [{"target_kind": "vyadhi", "name": "Z", "weight": 1.0}],
    }
    findings = [{"param": "P", "finding": "f-required"}]
    findings += [{"param": f"P{i}", "finding": f"f{i}"} for i in range(10)]
    out = score_findings(findings, [huge_pattern])
    assert out[0]["score"] <= 2.0


def test_multiple_patterns_summing_into_same_candidate():
    p1 = _madhumeha_pattern()
    p2 = {
        "name": "Madhumeha alt-rule",
        "pattern_type": "vyadhi",
        "conditions": [{"param": "Jihvā", "finding": "śveta-sthūla-snigdha", "required": True}],
        "targets": [{"target_kind": "vyadhi", "name": "Madhumeha", "weight": 0.5}],
    }
    findings = [
        {"param": "Mūtra", "finding": "madhura-mūtra"},
        {"param": "Jihvā", "finding": "śveta-sthūla-snigdha"},
    ]
    out = score_findings(findings, [p1, p2])
    madhu = next(c for c in out if c["name"] == "Madhumeha")
    assert madhu["score"] == pytest.approx(1.5, rel=1e-3)
    assert "Madhumeha kapha" in madhu["contributing_patterns"]
    assert "Madhumeha alt-rule" in madhu["contributing_patterns"]


def test_red_flags_propagate_to_candidates():
    findings = [{"param": "Mūtra", "finding": "madhura-mūtra"}]
    out = score_findings(findings, [_madhumeha_pattern()])
    assert "DKA — refer" in out[0]["red_flags"]


def test_candidates_sorted_by_score_descending():
    """Multiple targets, different rules, must be ranked correctly."""
    p_high = {
        "name": "high",
        "pattern_type": "vyadhi",
        "conditions": [{"param": "X", "finding": "a", "required": True}],
        "targets": [{"target_kind": "vyadhi", "name": "High", "weight": 5.0}],
    }
    p_low = {
        "name": "low",
        "pattern_type": "vyadhi",
        "conditions": [{"param": "X", "finding": "a", "required": True}],
        "targets": [{"target_kind": "vyadhi", "name": "Low", "weight": 0.5}],
    }
    findings = [{"param": "X", "finding": "a"}]
    out = score_findings(findings, [p_high, p_low])
    assert [c["name"] for c in out] == ["High", "Low"]


def test_score_findings_handles_dict_pattern_input():
    """Patterns passed as plain dicts (vs ORM rows) must score identically."""
    findings = [{"param": "Nāḍī", "finding": "vāta-nāḍī"}]
    out = score_findings(findings, [_vata_pattern()])
    assert out and out[0]["score"] == 1.0


def test_findings_to_set_strips_whitespace_and_drops_blanks():
    out = _findings_to_set([
        {"param": " A ", "finding": " b "},
        {"param": "", "finding": "x"},
        {"param": "X"},  # missing finding
    ])
    assert out == {("A", "b")}


def test_score_findings_returns_score_rationale_and_chikitsa():
    findings = [{"param": "Nāḍī", "finding": "vāta-nāḍī"}]
    out = score_findings(findings, [_vata_pattern()])
    cand = out[0]
    assert "Nāḍī is decisive." in cand["rationale"]
    assert cand["suggested_chikitsa"] == ["Anuvāsana Basti"]
