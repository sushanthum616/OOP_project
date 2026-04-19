from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.domain.models import Money, Product
from backend.app.persistence.models import ProductORM


class SqlAlchemyProductRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_active(self) -> List[Product]:
        stmt = (
            select(ProductORM)
            .where(ProductORM.is_active == True)  # noqa: E712
            .order_by(ProductORM.name.asc())
        )
        rows = self._db.scalars(stmt).all()
        return [self._to_domain(r) for r in rows]

    def get_by_id(self, product_id: UUID) -> Optional[Product]:
        row = self._db.get(ProductORM, str(product_id))
        return self._to_domain(row) if row else None
    

    def list_all(self) -> List[Product]:
        stmt = select(ProductORM).order_by(ProductORM.name.asc())
        rows = self._db.scalars(stmt).all()
        return [self._to_domain(r) for r in rows]

    def get_by_sku(self, sku: str) -> Optional[Product]:
        sku_norm = sku.strip()
        stmt = select(ProductORM).where(ProductORM.sku == sku_norm)
        row = self._db.scalars(stmt).first()
        return self._to_domain(row) if row else None

    def add(self, product: Product) -> None:
        row = ProductORM(
            id=str(product.id),
            sku=product.sku,
            name=product.name,
            description=product.description,
            price_currency=product.price.currency,
            price_cents=product.price.cents,
            quantity_available=product.quantity_available,
            is_active=product.is_active,
        )
        self._db.add(row)

    def save(self, product: Product) -> None:
        row = self._db.get(ProductORM, str(product.id))
        if not row:
            # treat as insert
            self.add(product)
            return

        row.sku = product.sku
        row.name = product.name
        row.description = product.description
        row.price_currency = product.price.currency
        row.price_cents = product.price.cents
        row.quantity_available = product.quantity_available
        row.is_active = product.is_active

    @staticmethod
    def _to_domain(row: ProductORM) -> Product:
        return Product(
            id=UUID(row.id),
            sku=row.sku,
            name=row.name,
            description=row.description,
            price=Money(currency=row.price_currency, cents=row.price_cents),
            quantity_available=row.quantity_available,
            is_active=row.is_active,
        )