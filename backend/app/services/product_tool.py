"""Product-recommendation tool exposed to the grounded chat LLM.

Schema definition + executor. The LLM decides when to call this based on the
tool description; we don't pattern-match the user's message. The tool returns
a small ranked list (id, name, why, price, image_url, shopify_url) for both
the LLM (so it can reference products in prose) and the API response (so the
widget can render product cards).

Lookup logic reuses the existing static product catalog and concept mappings
in app/data — same source of truth as the rule-based static_chat engine.
"""
from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

_products: list[dict] = []
_mappings: dict = {}


def _load() -> None:
    global _products, _mappings
    if _products:
        return
    with open(DATA_DIR / "products.json") as f:
        _products = json.load(f)
    with open(DATA_DIR / "product_mappings.json") as f:
        _mappings = json.load(f)


PRODUCT_TOOL: dict = {
    "name": "recommend_age_ayurveda_products",
    "description": (
        "Recommend AGE Ayurveda products from the live catalog that match a "
        "user's wellness concern and (optionally) constitutional type (dosha). "
        "Call this tool when the user asks for a product recommendation, asks "
        "what to take/buy for a condition, or describes a clear wellness "
        "concern (sleep, digestion, stress, immunity, joint pain, skin, hair, "
        "respiratory, women's health, focus). DO NOT call this tool for "
        "purely educational questions about Ayurvedic concepts — only when a "
        "product recommendation would be useful. Returns up to 4 products "
        "ranked by relevance, including a one-sentence reason for each."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "concern": {
                "type": "string",
                "description": (
                    "Primary wellness concern in 1-3 words. Examples: 'sleep', "
                    "'digestion', 'stress', 'immunity', 'joint pain', 'acidity', "
                    "'skin', 'hair fall', 'respiratory', 'focus', 'women's "
                    "health', 'weight'."
                ),
            },
            "dosha": {
                "type": "string",
                "enum": ["vata", "pitta", "kapha", "unknown"],
                "description": (
                    "User's primary dosha if mentioned or clearly inferable from "
                    "the question. Use 'unknown' if not stated."
                ),
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 6,
                "default": 3,
            },
        },
        "required": ["concern", "dosha"],
    },
}


_CONCERN_KEYWORD_MAP = {
    "sleep": ["sleep", "insomnia", "restless"],
    "digestion": ["digest", "constipation", "bloat", "gas", "appetite", "bowel"],
    "acidity": ["acidity", "heartburn", "hyperacid", "acid"],
    "stress": ["stress", "anxi", "tension", "nerve", "calm"],
    "immunity": ["immun", "cold", "cough", "flu", "respiratory"],
    "joint pain": ["joint", "arthrit", "muscle", "stiffness", "back pain", "knee"],
    "skin": ["skin", "acne", "complexion", "glow", "wrinkle", "pigment"],
    "hair fall": ["hair", "scalp", "dandruff", "balding"],
    "respiratory": ["respiratory", "breath", "sinus", "throat", "lung", "nasal"],
    "focus": ["focus", "concentration", "memory", "brain", "adhd", "cognitive"],
    "weight": ["weight", "fat", "obesity", "metabolism", "sugar", "diabetes"],
    "women's health": ["women", "period", "menstrual", "pcos", "hormonal"],
}


def _score_product(product: dict, concern_terms: list[str], dosha: str | None) -> float:
    score = 0.0

    benefits_lower = " ".join(product.get("benefits", [])).lower()
    category_lower = product.get("category", "").lower()
    desc_lower = product.get("description", "").lower()
    name_lower = product.get("name", "").lower()

    for term in concern_terms:
        if term in benefits_lower:
            score += 4
        if term in category_lower:
            score += 3
        if term in desc_lower:
            score += 2
        if term in name_lower:
            score += 5

    slug = product.get("slug")
    if slug and slug in _mappings:
        mapping = _mappings[slug]
        for concept in mapping.get("concepts", []):
            for term in concern_terms:
                if term in concept:
                    score += 3
        for condition in mapping.get("conditions", []):
            for term in concern_terms:
                if term in condition:
                    score += 4

    if dosha and dosha != "unknown":
        product_doshas = product.get("doshas", [])
        if dosha in product_doshas:
            score += 2

    return score


def _format_product(product: dict, dosha: str | None) -> dict:
    why = product.get("dosha_balance") or product.get("description", "")[:160]
    if dosha and dosha != "unknown" and dosha in product.get("doshas", []):
        why = f"Suited for {dosha.capitalize()} types. " + why
    return {
        "id": product["id"],
        "name": product["name"],
        "slug": product["slug"],
        "why": why,
        "price": product.get("price"),
        "image_url": product.get("image_url"),
        "shopify_url": product.get("shopify_url"),
        "doshas": product.get("doshas", []),
    }


def execute_product_recommendation(input_data: dict) -> dict:
    """Execute the product recommendation tool.

    Returns a dict that's serialised straight back to Claude as the tool
    result. Same payload also surfaces in the API response so the widget
    can render product cards alongside the prose answer.
    """
    _load()

    concern = (input_data.get("concern") or "").lower().strip()
    dosha = (input_data.get("dosha") or "unknown").lower().strip()
    max_results = int(input_data.get("max_results") or 3)
    max_results = max(1, min(max_results, 6))

    concern_terms: list[str] = []
    for canonical, keywords in _CONCERN_KEYWORD_MAP.items():
        if concern in canonical or canonical in concern:
            concern_terms.extend(keywords)
        for kw in keywords:
            if kw in concern:
                concern_terms.extend(keywords)
                break
    if not concern_terms:
        concern_terms = [concern]
    concern_terms = list({t for t in concern_terms if t})

    scored: list[tuple[float, dict]] = []
    for product in _products:
        s = _score_product(product, concern_terms, dosha)
        if s > 0:
            scored.append((s, product))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:max_results]

    products = [_format_product(p, dosha) for _, p in top]

    return {
        "concern": concern,
        "dosha": dosha,
        "products": products,
        "count": len(products),
    }
