"""Dravya model + ingestion tests."""
import pytest
from sqlalchemy import select

from app.models import Dravya


async def test_dravya_can_be_inserted_with_full_schema(db_session):
    d = Dravya(
        nama_sanskrit="Aśvagandhā",
        nama_devanagari="अश्वगन्धा",
        latin_binomial="Withania somnifera",
        family="Solanaceae",
        english="Winter cherry",
        hindi="अश्वगंधा",
        varga_bhavaprakasha="Guḍūcyādi",
        part_used=["mūla"],
        rasa=["tikta", "kaṣāya", "madhura"],
        guna=["laghu", "snigdha"],
        virya="uṣṇa",
        vipaka="madhura",
        dosha_karma={"vata": "śāmaka", "pitta": "sama", "kapha": "śāmaka"},
        karma=["balya", "rasāyana", "medhya"],
        prayoga=["daurbalya", "anidrā"],
        matra_value="3-6",
        matra_unit="g",
        anupana=["dugdha", "ghṛta"],
        contraindications=["pregnancy"],
        nighantu_refs=["Bhāvaprakāśa, Guḍūcyādi varga"],
        review_tier="llm-only",
    )
    db_session.add(d)
    await db_session.commit()

    fetched = (await db_session.execute(
        select(Dravya).where(Dravya.nama_sanskrit == "Aśvagandhā")
    )).scalar_one()

    assert fetched.latin_binomial == "Withania somnifera"
    assert fetched.rasa == ["tikta", "kaṣāya", "madhura"]
    assert fetched.dosha_karma["vata"] == "śāmaka"
    assert "balya" in fetched.karma
    assert fetched.review_tier == "llm-only"


async def test_dravya_default_review_tier_is_llm_only(db_session):
    d = Dravya(nama_sanskrit="Test", latin_binomial="Test test")
    db_session.add(d)
    await db_session.commit()
    fetched = (await db_session.execute(select(Dravya))).scalar_one()
    assert fetched.review_tier == "llm-only"


async def test_dravya_default_type_is_sthavara(db_session):
    d = Dravya(nama_sanskrit="Test", latin_binomial="Test test")
    db_session.add(d)
    await db_session.commit()
    fetched = (await db_session.execute(select(Dravya))).scalar_one()
    assert fetched.dravya_type == "sthāvara"


async def test_dravya_display_name_includes_latin(db_session):
    d = Dravya(nama_sanskrit="Aśvagandhā", latin_binomial="Withania somnifera")
    db_session.add(d)
    await db_session.commit()
    fetched = (await db_session.execute(select(Dravya))).scalar_one()
    assert fetched.display_name() == "Aśvagandhā (Withania somnifera)"


async def test_dravya_display_name_without_latin(db_session):
    d = Dravya(nama_sanskrit="Brāhmī")
    db_session.add(d)
    await db_session.commit()
    fetched = (await db_session.execute(select(Dravya))).scalar_one()
    assert fetched.display_name() == "Brāhmī"


# ---- ingestion script ---------------------------------------------------


async def test_ingest_dravyas_loads_seed_yaml(db_session, monkeypatch):
    """Confirm the actual seed YAML loads cleanly + Devanagari is generated."""
    from sqlalchemy import func as f
    from scripts.ingest_dravyas import _to_devanagari, _upsert_dravya
    import yaml
    from pathlib import Path

    seed_path = (
        Path(__file__).resolve().parent.parent
        / "app" / "data" / "dravyas" / "seed_top30.yaml"
    )
    assert seed_path.exists(), f"missing {seed_path}"
    doc = yaml.safe_load(seed_path.read_text())
    rows = doc["dravyas"]
    assert len(rows) >= 25  # we expect ~30 entries

    inserted = 0
    for row in rows:
        outcome = await _upsert_dravya(db_session, row, "seed_top30.yaml")
        if outcome == "inserted":
            inserted += 1
    await db_session.commit()
    assert inserted >= 25

    # Devanagari should be auto-generated for all
    rows_db = (await db_session.execute(select(Dravya))).scalars().all()
    for d in rows_db:
        assert d.nama_devanagari, f"missing Devanagari for {d.nama_sanskrit}"
        # Sanity-check Devanagari range
        assert any("ऀ" <= c <= "ॿ" for c in d.nama_devanagari)


async def test_ingest_dravyas_is_idempotent(db_session):
    """Re-running ingestion should update, not duplicate."""
    from scripts.ingest_dravyas import _upsert_dravya
    row = {
        "nama_sanskrit": "Tulasī",
        "latin_binomial": "Ocimum sanctum",
        "rasa": ["kaṭu", "tikta"],
    }
    out1 = await _upsert_dravya(db_session, row, "test")
    await db_session.commit()
    out2 = await _upsert_dravya(db_session, row, "test")
    await db_session.commit()
    assert out1 == "inserted"
    assert out2 == "updated"

    # Updated row replaces fields
    row3 = {
        "nama_sanskrit": "Tulasī",
        "latin_binomial": "Ocimum sanctum",
        "rasa": ["kaṭu", "tikta", "madhura"],  # changed
    }
    out3 = await _upsert_dravya(db_session, row3, "test")
    await db_session.commit()
    assert out3 == "updated"
    fetched = (await db_session.execute(select(Dravya).where(Dravya.nama_sanskrit == "Tulasī"))).scalar_one()
    assert "madhura" in fetched.rasa


async def test_devanagari_transliteration_handles_capital_iast():
    """vidyut needs lowercase IAST — our wrapper lowercases first."""
    from scripts.ingest_dravyas import _to_devanagari
    out = _to_devanagari("Aśvagandhā")
    assert out is not None
    # Should NOT contain a stray uppercase Roman A
    assert "A" not in out
    # Should be all Devanagari
    for c in out:
        assert "ऀ" <= c <= "ॿ", f"non-Devanagari char {c!r}"


async def test_devanagari_handles_none():
    from scripts.ingest_dravyas import _to_devanagari
    assert _to_devanagari(None) is None
    assert _to_devanagari("") is None
