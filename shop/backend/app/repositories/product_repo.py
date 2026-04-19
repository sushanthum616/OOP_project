from __future__ import annotations

from typing import Dict, List, Optional, Protocol
from uuid import UUID

from backend.app.domain.models import Product


class ProductRepository(Protocol):
    def list_active(self) -> List[Product]:
        ...

    def get_by_id(self, product_id: UUID) -> Optional[Product]:
        ...

    def list_all(self) -> List[Product]:
        ...

    def get_by_sku(self, sku: str) -> Optional[Product]:
        ...

    def add(self, product: Product) -> None:
        ...

    def save(self, product: Product) -> None:
        ...


class InMemoryProductRepository:
    def __init__(self) -> None:
        self._products: Dict[UUID, Product] = {}

    def list_active(self) -> List[Product]:
        return [p for p in self._products.values() if p.is_active]

    def get_by_id(self, product_id: UUID) -> Optional[Product]:
        return self._products.get(product_id)
    
    def list_all(self) -> List[Product]:
       return list(self._products.values())

    def get_by_sku(self, sku: str) -> Optional[Product]:
        sku_norm = sku.strip()
        for p in self._products.values():
            if p.sku == sku_norm:
                return p
        return None

    def add(self, product: Product) -> None:
        self._products[product.id] = product

    def save(self, product: Product) -> None:
        self._products[product.id] = product