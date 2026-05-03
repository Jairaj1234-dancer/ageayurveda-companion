"""Vyādhi model + ingestion tests."""
import pytest
from sqlalchemy import select

from app.models import Vyadhi


async def test_vyadhi_inserts_with_full_schema(db_session):
    v = Vyadhi(
        nama_sanskrit="Madhumeha",
        nama_devanagari="मधुमेह",
        english="Madhumeha (≈ Type 2 DM)",
        hindi="मधुमेह",
        synonyms=["Vātaja-prameha"],
        chapter="Prameha",
        namaste_code="AAA-1.2.3",
        icd11_tm2_code="SK04.0",
        icd11_main_code="5A11",
        dosha_typology=["vātaja", "kaphaja"],
        primary_dosha="vāta",
        primary_dushya=["meda", "māṃsa"],
        srotas=["mūtravaha"],
        nidana=["excess sweet food"],
        purva_rupa=["sweet urine"],
        rupa=["polyuria"],
        sadhya_asadhya="kṛcchra-sādhya",
        common_formulations=["Triphalā guggulu"],
        common_dravyas=["Haridrā"],
        modern_diagnostics=["HbA1c"],
        red_flags_for_referral=["DKA"],
        review_tier="llm-only",
    )
    db_session.add(v)
    await db_session.commit()
    fetched = (await db_session.execute(
        select(Vyadhi).where(Vyadhi.nama_sanskrit == "Madhumeha")
    )).scalar_one()
    assert fetched.icd11_main_code == "5A11"
    assert fetched.primary_dosha == "vāta"
    assert "polyuria" in fetched.rupa


async def test_vyadhi_default_review_tier(db_session):
    v = Vyadhi(nama_sanskrit="Test")
    db_session.add(v)
    await db_session.commit()
    fetched = (await db_session.execute(select(Vyadhi))).scalar_one()
    assert fetched.review_tier == "llm-only"


async def test_vyadhi_optional_codes_can_be_null(db_session):
    """Most rows ship without NAMASTE codes until portal access is negotiated."""
    v = Vyadhi(nama_sanskrit="Test", chapter="Test-vyādhi")
    db_session.add(v)
    await db_session.commit()
    fetched = (await db_session.execute(select(Vyadhi))).scalar_one()
    assert fetched.namaste_code is None
    assert fetched.icd11_tm2_code is None
    assert fetched.icd11_main_code is None


# ---- ingestion tests --------------------------------------------------


async def test_vyadhi_seed_yaml_loads(db_session):
    from scripts.ingest_vyadhi import _upsert_vyadhi
    import yaml
    from pathlib import Path

    seed = (
        Path(__file__).resolve().parent.parent
        / "app" / "data" / "vyadhi" / "seed_top30.yaml"
    )
    assert seed.exists()
    doc = yaml.safe_load(seed.read_text())
    rows = doc["vyadhi"]
    assert len(rows) >= 25

    for row in rows:
        await _upsert_vyadhi(db_session, row, "seed_top30.yaml")
    await db_session.commit()

    n = (await db_session.execute(select(Vyadhi))).scalars().all()
    assert len(n) >= 25

    # Devanagari should be auto-generated
    for v in n:
        assert v.nama_devanagari, f"missing Devanagari for {v.nama_sanskrit}"
        assert any("ऀ" <= c <= "ॿ" for c in v.nama_devanagari)


async def test_vyadhi_ingest_idempotent(db_session):
    from scripts.ingest_vyadhi import _upsert_vyadhi
    row = {"nama_sanskrit": "Test", "chapter": "Test-vyādhi"}
    out1 = await _upsert_vyadhi(db_session, row, "test")
    await db_session.commit()
    out2 = await _upsert_vyadhi(db_session, row, "test")
    await db_session.commit()
    assert out1 == "inserted"
    assert out2 == "updated"

    n = (await db_session.execute(select(Vyadhi))).scalars().all()
    assert len(n) == 1


async def test_vyadhi_ingest_updates_existing(db_session):
    from scripts.ingest_vyadhi import _upsert_vyadhi
    await _upsert_vyadhi(db_session, {"nama_sanskrit": "Test", "primary_dosha": "vāta"}, "t")
    await db_session.commit()
    await _upsert_vyadhi(db_session, {"nama_sanskrit": "Test", "primary_dosha": "pitta"}, "t")
    await db_session.commit()
    fetched = (await db_session.execute(select(Vyadhi))).scalar_one()
    assert fetched.primary_dosha == "pitta"


async def test_vyadhi_skips_rows_without_name(db_session):
    from scripts.ingest_vyadhi import _upsert_vyadhi
    out = await _upsert_vyadhi(db_session, {"chapter": "x"}, "t")
    assert out == "skipped"
