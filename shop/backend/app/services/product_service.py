from __future__ import annotations

from typing import List
from uuid import UUID

from backend.app.domain.models import Product
from backend.app.repositories.product_repo import ProductRepository


class ProductService:
    def __init__(self, repo: ProductRepository) -> None:
        self._repo = repo

    def list_products(self, q: str | None = None) -> List[Product]:
        products = self._repo.list_active()
        if not q:
            return products

        needle = q.strip().lower()
        if not needle:
            return products

        def matches(p: Product) -> bool:
            return (
                needle in p.name.lower()
                or needle in p.description.lower()
                or needle in p.sku.lower()
            )

        return [p for p in products if matches(p)]

    def get_product(self, product_id: UUID) -> Product:
        product = self._repo.get_by_id(product_id)
        if product is None or not product.is_active:
            raise KeyError("Product not found")
        return product