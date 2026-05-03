"""Seed products from products.json into the database."""
import asyncio
import json
import sys
import os
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import AsyncSessionLocal, engine, Base
from app.models.product import Product


async def main():
    data_path = os.path.join(os.path.dirname(__file__), "..", "app", "data", "products.json")

    with open(data_path) as f:
        products = json.load(f)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        for p in products:
            product = Product(
                id=uuid.uuid4(),
                name=p["name"],
                name_hi=p.get("name_hi"),
                slug=p["slug"],
                description=p.get("description"),
                description_hi=p.get("description_hi"),
                price=p.get("price"),
                image_url=p.get("image_url"),
                shopify_url=p.get("shopify_url"),
                category=p.get("category"),
                ingredients=p.get("ingredients"),
                benefits=p.get("benefits"),
                doshas=p.get("doshas"),
            )
            session.add(product)

        await session.commit()
        print(f"Seeded {len(products)} products.")


if __name__ == "__main__":
    asyncio.run(main())
