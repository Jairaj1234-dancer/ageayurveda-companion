"""ParikshaParam + DiagnosticPattern model + ingestion tests."""
import pytest
from pathlib import Path
import yaml
from sqlalchemy import select

from app.models import ParikshaParam, DiagnosticPattern


# ---- model -----------------------------------------------------------


async def test_param_inserts_with_full_schema(db_session):
    p = ParikshaParam(
        name_iast="Nāḍī",
        name_devanagari="नाडी",
        english="Pulse",
        schema_family="aṣṭa-vidha",
        domain="physical",
        examination_method="Three fingers on radial pulse.",
        findings=[
            {"value": "vāta-nāḍī", "implies": {"vata": "+", "pitta": "0", "kapha": "0"}},
            {"value": "pitta-nāḍī", "implies": {"vata": "0", "pitta": "+", "kapha": "0"}},
        ],
        normal_finding="sama-nāḍī",
        review_tier="llm-only",
    )
    db_session.add(p)
    await db_session.commit()

    fetched = (await db_session.execute(
        select(ParikshaParam).where(ParikshaParam.name_iast == "Nāḍī")
    )).scalar_one()
    assert fetched.schema_family == "aṣṭa-vidha"
    assert fetched.findings[0]["implies"]["vata"] == "+"
    assert fetched.normal_finding == "sama-nāḍī"


async def test_pattern_inserts_with_full_schema(db_session):
    p = DiagnosticPattern(
        name="Vāta-prakopa core",
        pattern_type="dosha-state",
        conditions=[
            {"param": "Nāḍī", "finding": "vāta-nāḍī", "required": True},
        ],
        targets=[
            {"target_kind": "dosha-state", "name": "vāta-vṛddhi", "weight": 1.0},
        ],
        suggested_chikitsa=["Anuvāsana Basti"],
        evidence_grade="C",
        review_tier="llm-only",
    )
    db_session.add(p)
    await db_session.commit()
    fetched = (await db_session.execute(select(DiagnosticPattern))).scalar_one()
    assert fetched.pattern_type == "dosha-state"
    assert fetched.targets[0]["name"] == "vāta-vṛddhi"


# ---- ingestion -------------------------------------------------------


SEED_DIR = (
    Path(__file__).resolve().parent.parent / "app" / "data" / "pariksha"
)


async def test_param_seed_yaml_loads(db_session):
    from scripts.ingest_pariksha import _upsert_param

    seed = SEED_DIR / "seed_params.yaml"
    assert seed.exists()
    rows = yaml.safe_load(seed.read_text())["pariksha_params"]
    # All three classical schemas + extras must be represented.
    assert len(rows) >= 20

    for row in rows:
        await _upsert_param(db_session, row, "seed_params.yaml")
    await db_session.commit()

    fetched = (await db_session.execute(select(ParikshaParam))).scalars().all()
    assert len(fetched) >= 20

    families = {p.schema_family for p in fetched}
    for required in ("aṣṭa-vidha", "daśa-vidha", "trividha"):
        assert required in families, f"missing seed entries for {required}"

    # Devanagari auto-generated for IAST names.
    for p in fetched:
        assert p.name_devanagari, f"missing Devanagari for {p.name_iast}"


async def test_pattern_seed_yaml_loads(db_session):
    from scripts.ingest_pariksha import _upsert_pattern

    seed = SEED_DIR / "seed_patterns.yaml"
    assert seed.exists()
    rows = yaml.safe_load(seed.read_text())["diagnostic_patterns"]
    assert len(rows) >= 5

    for row in rows:
        await _upsert_pattern(db_session, row, "seed_patterns.yaml")
    await db_session.commit()

    fetched = (await db_session.execute(select(DiagnosticPattern))).scalars().all()
    assert len(fetched) >= 5

    types = {p.pattern_type for p in fetched}
    assert "dosha-state" in types
    assert "vyadhi" in types


async def test_param_ingest_idempotent(db_session):
    from scripts.ingest_pariksha import _upsert_param
    row = {"name_iast": "Test", "schema_family": "extra"}
    out1 = await _upsert_param(db_session, row, "test")
    await db_session.commit()
    out2 = await _upsert_param(db_session, row, "test")
    await db_session.commit()
    assert out1 == "inserted"
    assert out2 == "updated"

    n = (await db_session.execute(select(ParikshaParam))).scalars().all()
    assert len(n) == 1


async def test_pattern_ingest_idempotent(db_session):
    from scripts.ingest_pariksha import _upsert_pattern
    row = {
        "name": "Test pattern",
        "pattern_type": "vyadhi",
        "conditions": [{"param": "X", "finding": "y", "required": True}],
        "targets": [{"target_kind": "vyadhi", "name": "Z", "weight": 1.0}],
    }
    out1 = await _upsert_pattern(db_session, row, "test")
    await db_session.commit()
    out2 = await _upsert_pattern(db_session, row, "test")
    await db_session.commit()
    assert out1 == "inserted"
    assert out2 == "updated"


async def test_param_skips_rows_without_required_fields(db_session):
    from scripts.ingest_pariksha import _upsert_param
    assert await _upsert_param(db_session, {}, "t") == "skipped"
    assert await _upsert_param(db_session, {"name_iast": "X"}, "t") == "skipped"


async def test_pattern_skips_rows_without_required_fields(db_session):
    from scripts.ingest_pariksha import _upsert_pattern
    assert await _upsert_pattern(db_session, {"name": "X"}, "t") == "skipped"
    assert await _upsert_pattern(
        db_session, {"name": "X", "conditions": []}, "t"
    ) == "skipped"
    assert await _upsert_pattern(
        db_session,
        {"name": "X", "conditions": [{"param": "a"}], "targets": []},
        "t",
    ) == "skipped"
