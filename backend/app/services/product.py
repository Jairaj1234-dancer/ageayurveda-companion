import json
import os

from app.core.logging import logger

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def load_product_mappings() -> dict:
    path = os.path.join(DATA_DIR, "product_mappings.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def load_products() -> list[dict]:
    path = os.path.join(DATA_DIR, "products.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []


PRODUCT_MAPPINGS = load_product_mappings()
PRODUCTS = {p["slug"]: p for p in load_products()}


def recommend_products(
    query: str,
    response_text: str,
    dosha: str | None = None,
    max_results: int = 2,
) -> list[dict]:
    """Score and recommend products based on query context."""
    if not PRODUCT_MAPPINGS:
        return []

    combined_text = f"{query} {response_text}".lower()
    scores: dict[str, float] = {}

    for slug, mapping in PRODUCT_MAPPINGS.items():
        score = 0.0

        for concept in mapping.get("concepts", []):
            if concept.lower() in combined_text:
                score += 3.0

        for condition in mapping.get("conditions", []):
            if condition.lower() in combined_text:
                score += 5.0

        for herb in mapping.get("herbs", []):
            if herb.lower() in combined_text:
                score += 4.0

        if dosha and dosha.lower() in [d.lower() for d in mapping.get("doshas", [])]:
            score += 2.0

        # Check blacklist
        for blacklisted in mapping.get("blacklist", []):
            if blacklisted.lower() in combined_text:
                score = 0.0
                break

        if score > 0:
            scores[slug] = score

    sorted_products = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    results = []
    for slug, score in sorted_products[:max_results]:
        if score < 3.0:  # minimum threshold
            continue
        product = PRODUCTS.get(slug, {})
        if product:
            results.append({
                "id": product.get("id", slug),
                "name": product.get("name", slug),
                "slug": slug,
                "price": product.get("price"),
                "image_url": product.get("image_url"),
                "shopify_url": product.get("shopify_url"),
                "score": score,
            })

    return results
