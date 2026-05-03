"""Formulation + FormulationIngredient model and ingestion tests."""
import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Dravya, Formulation, FormulationIngredient


async def test_formulation_inserts_with_full_schema(db_session):
    f = Formulation(
        name_iast="Triphalā Curṇa",
        name_devanagari="त्रिफला चूर्ण",
        english="Triphala Powder",
        kalpana_type="curṇa",
        primary_indication="Constipation, eye health",
        indications=["malabaddhatā", "akṣiroga"],
        dosha_action={"vata": "śāmaka", "pitta": "śāmaka", "kapha": "śāmaka"},
        karma=["anulomana", "rasāyana"],
        dose_value="3-6",
        dose_unit="g",
        anupana=["uṣṇa-jala"],
        contraindications=["pregnancy"],
        afi_ref="AFI Vol I, Sec 7:14",
        classical_source="Sharangadhara Saṃhitā Madhyama Khaṇḍa 6",
        review_tier="llm-only",
    )
    db_session.add(f)
    await db_session.commit()
    fetched = (await db_session.execute(
        select(Formulation).where(Formulation.name_iast == "Triphalā Curṇa")
    )).scalar_one()
    assert fetched.kalpana_type == "curṇa"
    assert fetched.indications == ["malabaddhatā", "akṣiroga"]
    assert fetched.dosha_action["pitta"] == "śāmaka"
    assert fetched.review_tier == "llm-only"


async def test_formulation_default_review_tier(db_session):
    f = Formulation(name_iast="Test", kalpana_type="curṇa")
    db_session.add(f)
    await db_session.commit()
    fetched = (await db_session.execute(select(Formulation))).scalar_one()
    assert fetched.review_tier == "llm-only"


async def test_formulation_ingredients_relationship(db_session):
    f = Formulation(name_iast="Trikaṭu", kalpana_type="curṇa")
    db_session.add(f)
    await db_session.flush()
    db_session.add_all([
        FormulationIngredient(
            formulation_id=f.id, ingredient_name="Śuṇṭhī", proportion="1 part", position=0
        ),
        FormulationIngredient(
            formulation_id=f.id, ingredient_name="Marica", proportion="1 part", position=1
        ),
        FormulationIngredient(
            formulation_id=f.id, ingredient_name="Pippalī", proportion="1 part", position=2
        ),
    ])
    await db_session.commit()

    fetched = (await db_session.execute(
        select(Formulation).where(Formulation.name_iast == "Trikaṭu")
        .options(selectinload(Formulation.ingredients))
    )).scalar_one()
    assert len(fetched.ingredients) == 3
    assert [ing.ingredient_name for ing in fetched.ingredients] == ["Śuṇṭhī", "Marica", "Pippalī"]


async def test_formulation_cascade_deletes_ingredients(db_session):
    f = Formulation(name_iast="Test", kalpana_type="curṇa")
    db_session.add(f)
    await db_session.flush()
    db_session.add(FormulationIngredient(
        formulation_id=f.id, ingredient_name="Test ingredient", position=0,
    ))
    await db_session.commit()

    await db_session.delete(f)
    await db_session.commit()

    n = (await db_session.execute(select(FormulationIngredient))).scalars().all()
    assert len(n) == 0


# ---- ingestion tests --------------------------------------------------


async def test_extended_seed_yaml_loads_and_covers_all_kalpana_types(db_session):
    """seed_extended.yaml must load cleanly and span all major kalpana types."""
    from scripts.ingest_formulations import _upsert_formulation, _add_ingredients
    import yaml
    from pathlib import Path

    seed = (
        Path(__file__).resolve().parent.parent
        / "app" / "data" / "formulations" / "seed_extended.yaml"
    )
    assert seed.exists()
    rows = yaml.safe_load(seed.read_text())["formulations"]
    assert len(rows) >= 30

    for row in rows:
        outcome, formulation = await _upsert_formulation(
            db_session, row, "seed_extended.yaml"
        )
        if formulation is not None:
            await _add_ingredients(db_session, formulation, row.get("ingredients") or [])
    await db_session.commit()

    from app.models import Formulation
    from sqlalchemy import select
    fetched = (await db_session.execute(select(Formulation))).scalars().all()
    kalpana_types = {f.kalpana_type for f in fetched}
    # Must include the broader set introduced in the extended seed.
    for required in ("curṇa", "guggulu", "rasa", "vaṭī", "avaleha", "ghṛta", "taila", "ariṣṭa"):
        assert required in kalpana_types, f"missing kalpana_type {required}"


async def test_ingest_formulations_seed_yaml_loads(db_session):
    from scripts.ingest_formulations import _upsert_formulation, _add_ingredients
    import yaml
    from pathlib import Path

    seed = (
        Path(__file__).resolve().parent.parent
        / "app" / "data" / "formulations" / "seed_classical.yaml"
    )
    assert seed.exists()
    doc = yaml.safe_load(seed.read_text())
    rows = doc["formulations"]
    assert len(rows) >= 15

    inserted = 0
    total_ingredients = 0
    for row in rows:
        outcome, formulation = await _upsert_formulation(db_session, row, "seed_classical.yaml")
        if outcome == "inserted":
            inserted += 1
        if formulation is not None:
            total_ingredients += await _add_ingredients(db_session, formulation, row.get("ingredients") or [])
    await db_session.commit()

    assert inserted >= 15
    assert total_ingredients > 50  # We expect ~100 ingredient rows total

    # Devanagari auto-generated for any row that didn't ship one
    rows_db = (await db_session.execute(select(Formulation))).scalars().all()
    for f in rows_db:
        assert f.name_devanagari, f"missing Devanagari for {f.name_iast}"


async def test_upsert_tolerates_kalpana_reclassification(db_session):
    """If a yoga gets reclassified (e.g. mistagged 'vaṭī' → corrected 'guggulu')
    on re-ingest, the upsert must update the existing row by name_iast rather
    than create a second row. Regression test for an early seed bug."""
    from scripts.ingest_formulations import _upsert_formulation
    from app.models import Formulation

    out1, f1 = await _upsert_formulation(
        db_session,
        {"name_iast": "Test Yoga", "kalpana_type": "vaṭī"},
        "test",
    )
    await db_session.commit()
    assert out1 == "inserted"

    out2, f2 = await _upsert_formulation(
        db_session,
        {"name_iast": "Test Yoga", "kalpana_type": "guggulu"},
        "test",
    )
    await db_session.commit()
    assert out2 == "updated"
    assert f1.id == f2.id

    rows = (await db_session.execute(
        select(Formulation).where(Formulation.name_iast == "Test Yoga")
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].kalpana_type == "guggulu"


async def test_ingest_idempotent_upsert(db_session):
    from scripts.ingest_formulations import _upsert_formulation, _add_ingredients
    row = {
        "name_iast": "Test Curṇa",
        "kalpana_type": "curṇa",
        "primary_indication": "test",
        "ingredients": [{"ingredient_name": "Pippalī", "proportion": "1 part"}],
    }
    out1, f1 = await _upsert_formulation(db_session, row, "test")
    await _add_ingredients(db_session, f1, row["ingredients"])
    await db_session.commit()

    # Re-run with same row — should update, not duplicate
    out2, f2 = await _upsert_formulation(db_session, row, "test")
    await _add_ingredients(db_session, f2, row["ingredients"])
    await db_session.commit()

    assert out1 == "inserted"
    assert out2 == "updated"
    assert f1.id == f2.id

    # Ingredients should not duplicate (re-insert wipes old then adds new)
    n = (await db_session.execute(
        select(FormulationIngredient).where(FormulationIngredient.formulation_id == f2.id)
    )).scalars().all()
    assert len(n) == 1


async def test_ingredient_resolves_to_dravya_when_present(db_session):
    """If a Dravya with matching name exists, the ingredient resolves to it."""
    from scripts.ingest_formulations import _resolve_dravya, _upsert_formulation, _add_ingredients

    # Seed a known dravya
    db_session.add(Dravya(nama_sanskrit="Pippalī", latin_binomial="Piper longum"))
    await db_session.commit()

    resolved_id = await _resolve_dravya(db_session, "Pippalī")
    assert resolved_id is not None

    # And via the full pipeline
    row = {
        "name_iast": "Test",
        "kalpana_type": "curṇa",
        "ingredients": [{"ingredient_name": "Pippalī", "proportion": "1 part"}],
    }
    _, f = await _upsert_formulation(db_session, row, "test")
    await _add_ingredients(db_session, f, row["ingredients"])
    await db_session.commit()

    ing = (await db_session.execute(
        select(FormulationIngredient).where(FormulationIngredient.formulation_id == f.id)
    )).scalar_one()
    assert ing.dravya_id == resolved_id


async def test_unresolved_ingredient_keeps_null_dravya(db_session):
    """Unknown ingredients still ingest with dravya_id=NULL."""
    from scripts.ingest_formulations import _upsert_formulation, _add_ingredients
    row = {
        "name_iast": "Test",
        "kalpana_type": "curṇa",
        "ingredients": [{"ingredient_name": "Completely unknown ingredient xyzzy"}],
    }
    _, f = await _upsert_formulation(db_session, row, "test")
    await _add_ingredients(db_session, f, row["ingredients"])
    await db_session.commit()

    ing = (await db_session.execute(
        select(FormulationIngredient).where(FormulationIngredient.formulation_id == f.id)
    )).scalar_one()
    assert ing.dravya_id is None
    assert ing.ingredient_name.startswith("Completely unknown")
