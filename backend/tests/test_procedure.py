"""Procedure model + ingestion tests."""
import pytest
from sqlalchemy import select

from app.models import Procedure


# ---- model -----------------------------------------------------------


async def test_procedure_inserts_with_full_schema(db_session):
    p = Procedure(
        name_iast="Vamana",
        name_devanagari="वमन",
        english="Therapeutic emesis",
        hindi="वमन",
        category="panchakarma",
        practitioner_level="vaidya-only",
        primary_indication="Kapha-pradhāna vyādhi",
        indications=["tamaka śvāsa", "pīnasa"],
        dosha_action={"vata": "vardhaka", "pitta": "sama", "kapha": "śāmaka"},
        contraindications=["garbhiṇī", "bāla"],
        purva_karma=[{"step": "Snehapāna", "duration": "3-7 days"}],
        pradhana_karma=[{"step": "Vamanopaga drink"}],
        paschat_karma=[{"step": "Saṃsarjana-krama"}],
        common_dravyas=["Madanaphala", "Yaṣṭimadhu"],
        duration_days=7,
        season=["vasanta"],
        adverse_events=["mūrcchā"],
        red_flags=["bleeding in vomitus"],
        classical_source="Caraka Sūtra 15",
        review_tier="llm-only",
    )
    db_session.add(p)
    await db_session.commit()

    fetched = (await db_session.execute(
        select(Procedure).where(Procedure.name_iast == "Vamana")
    )).scalar_one()
    assert fetched.category == "panchakarma"
    assert fetched.practitioner_level == "vaidya-only"
    assert fetched.dosha_action["kapha"] == "śāmaka"
    assert "garbhiṇī" in fetched.contraindications
    assert fetched.duration_days == 7


async def test_procedure_default_review_tier(db_session):
    p = Procedure(name_iast="Test", category="caryā")
    db_session.add(p)
    await db_session.commit()
    fetched = (await db_session.execute(select(Procedure))).scalar_one()
    assert fetched.review_tier == "llm-only"
    assert fetched.practitioner_level == "vaidya-only"  # conservative default


async def test_procedure_display_name():
    p = Procedure(name_iast="Vamana", english="Therapeutic emesis", category="panchakarma")
    assert "Vamana" in p.display_name()
    assert "Therapeutic emesis" in p.display_name()


async def test_procedure_display_name_when_english_matches():
    p = Procedure(name_iast="Same", english="Same", category="caryā")
    assert p.display_name() == "Same"


# ---- ingestion --------------------------------------------------------


async def test_procedure_seed_yaml_loads(db_session):
    from scripts.ingest_procedures import _upsert_procedure
    import yaml
    from pathlib import Path

    seed = (
        Path(__file__).resolve().parent.parent
        / "app" / "data" / "procedures" / "seed_top30.yaml"
    )
    assert seed.exists()
    doc = yaml.safe_load(seed.read_text())
    rows = doc["procedures"]
    assert len(rows) >= 25

    for row in rows:
        await _upsert_procedure(db_session, row, "seed_top30.yaml")
    await db_session.commit()

    n = (await db_session.execute(select(Procedure))).scalars().all()
    assert len(n) >= 25

    # Devanagari should be auto-generated
    for p in n:
        assert p.name_devanagari, f"missing Devanagari for {p.name_iast}"
        assert any("ऀ" <= c <= "ॿ" for c in p.name_devanagari)


async def test_procedure_seed_covers_all_main_categories(db_session):
    """The seed must seed at least one entry in each major category — the
    chatbot's procedure-suggestion logic depends on every category having
    real options to draw from."""
    from scripts.ingest_procedures import _upsert_procedure
    import yaml
    from pathlib import Path

    seed = (
        Path(__file__).resolve().parent.parent
        / "app" / "data" / "procedures" / "seed_top30.yaml"
    )
    rows = yaml.safe_load(seed.read_text())["procedures"]
    for row in rows:
        await _upsert_procedure(db_session, row, "seed_top30.yaml")
    await db_session.commit()

    cats = {p.category for p in (await db_session.execute(select(Procedure))).scalars().all()}
    for required in ("panchakarma", "purva-karma", "kriyā-bāhya", "caryā", "rasāyana"):
        assert required in cats, f"missing seed entries for category {required}"


async def test_procedure_ingest_idempotent(db_session):
    from scripts.ingest_procedures import _upsert_procedure
    row = {"name_iast": "Test", "category": "caryā"}
    out1 = await _upsert_procedure(db_session, row, "test")
    await db_session.commit()
    out2 = await _upsert_procedure(db_session, row, "test")
    await db_session.commit()
    assert out1 == "inserted"
    assert out2 == "updated"

    n = (await db_session.execute(select(Procedure))).scalars().all()
    assert len(n) == 1


async def test_procedure_ingest_updates_existing(db_session):
    from scripts.ingest_procedures import _upsert_procedure
    await _upsert_procedure(
        db_session,
        {"name_iast": "Test", "category": "caryā", "primary_indication": "Original"},
        "t",
    )
    await db_session.commit()
    await _upsert_procedure(
        db_session,
        {"name_iast": "Test", "category": "caryā", "primary_indication": "Updated"},
        "t",
    )
    await db_session.commit()
    fetched = (await db_session.execute(select(Procedure))).scalar_one()
    assert fetched.primary_indication == "Updated"


async def test_procedure_skips_rows_without_name(db_session):
    from scripts.ingest_procedures import _upsert_procedure
    out = await _upsert_procedure(db_session, {"category": "caryā"}, "t")
    assert out == "skipped"


async def test_procedure_skips_rows_without_category(db_session):
    """Category is the indexed pivot for category-filtered queries —
    refuse silent insert without one."""
    from scripts.ingest_procedures import _upsert_procedure
    out = await _upsert_procedure(db_session, {"name_iast": "X"}, "t")
    assert out == "skipped"
