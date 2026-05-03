"""Product-recommendation tool dispatch + ranking."""
from app.services.product_tool import (
    PRODUCT_TOOL,
    execute_product_recommendation,
)


def test_tool_schema_has_required_fields():
    assert PRODUCT_TOOL["name"] == "recommend_age_ayurveda_products"
    assert "description" in PRODUCT_TOOL
    schema = PRODUCT_TOOL["input_schema"]
    assert schema["type"] == "object"
    assert "concern" in schema["properties"]
    assert "dosha" in schema["properties"]
    assert schema["required"] == ["concern", "dosha"]


def test_dosha_enum_locked():
    enum = PRODUCT_TOOL["input_schema"]["properties"]["dosha"]["enum"]
    assert sorted(enum) == ["kapha", "pitta", "unknown", "vata"]


def test_recommend_for_sleep_and_vata_returns_sleep_aid_first():
    result = execute_product_recommendation({"concern": "sleep", "dosha": "vata"})
    names = [p["name"] for p in result["products"]]
    assert "Natural Sleep Aid" in names
    # Top result should be the sleep-specific product.
    assert names[0] == "Natural Sleep Aid"


def test_recommend_for_digestion_returns_digestive_products():
    result = execute_product_recommendation({"concern": "digestion", "dosha": "pitta"})
    names = [p["name"] for p in result["products"]]
    # Bowel Kare and Acid Relief are both digestive products.
    assert any(n in names for n in ["Bowel Kare", "Acid Relief"])


def test_recommend_for_joint_pain_returns_balm_or_haridra():
    result = execute_product_recommendation({"concern": "joint pain", "dosha": "kapha"})
    names = [p["name"] for p in result["products"]]
    assert any(n in names for n in ["Nitya Naturals Balm", "Haridra"])


def test_recommend_caps_at_max_results():
    result = execute_product_recommendation({
        "concern": "immunity",
        "dosha": "unknown",
        "max_results": 2,
    })
    assert len(result["products"]) <= 2


def test_recommend_unknown_concern_returns_empty():
    result = execute_product_recommendation({
        "concern": "completely unrelated nonsense xyzzy",
        "dosha": "unknown",
    })
    assert result["products"] == []


def test_returned_product_has_required_fields():
    result = execute_product_recommendation({"concern": "stress", "dosha": "vata"})
    assert result["products"], "Expected at least one product for stress + vata"
    p = result["products"][0]
    for key in ("id", "name", "slug", "why", "shopify_url"):
        assert key in p, f"missing key {key}"


def test_dosha_boost_promotes_matching_dosha():
    # 'sleep' + vata should rank Vata-suited products higher than Kapha-only.
    vata_result = execute_product_recommendation({"concern": "sleep", "dosha": "vata"})
    vata_names = [p["name"] for p in vata_result["products"]]
    # Natural Sleep Aid is Vata-suited; should be top.
    assert vata_names[0] == "Natural Sleep Aid"
