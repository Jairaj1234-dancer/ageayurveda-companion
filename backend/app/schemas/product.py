from pydantic import BaseModel


class ProductOut(BaseModel):
    id: str
    name: str
    name_hi: str | None
    slug: str
    description: str | None
    price: float | None
    image_url: str | None
    shopify_url: str | None
    category: str | None
    ingredients: list[str] | None
    benefits: list[str] | None
    doshas: list[str] | None

    model_config = {"from_attributes": True}
