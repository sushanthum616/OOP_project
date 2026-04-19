from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import UUID

from backend.app.domain.models import Money, Product
from backend.app.repositories.product_repo import ProductRepository


class AdminProductService:
    def __init__(self, repo: ProductRepository) -> None:
        self._repo = repo

    def create_product(
        self,
        *,
        sku: str,
        name: str,
        description: str,
        price_str: str,
        quantity_available: int,
        is_active: bool,
    ) -> Product:
        sku = sku.strip()
        name = name.strip()
        description = description.strip()

        if not sku:
            raise ValueError("SKU is required.")
        if not name:
            raise ValueError("Name is required.")
        if quantity_available < 0:
            raise ValueError("Quantity must be >= 0.")

        existing = self._repo.get_by_sku(sku)
        if existing:
            raise ValueError("SKU already exists. Use a unique SKU.")

        price = Money(currency="USD", cents=self._parse_price_to_cents(price_str))

        product = Product.create(
            sku=sku,
            name=name,
            description=description,
            price=price,
            quantity_available=quantity_available,
            is_active=is_active,
        )
        self._repo.add(product)
        return product

    def update_product(
        self,
        *,
        product_id: UUID,
        sku: str,
        name: str,
        description: str,
        price_str: str,
        quantity_available: int,
        is_active: bool,
    ) -> Product:
        product = self._repo.get_by_id(product_id)
        if not product:
            raise ValueError("Product not found.")

        sku = sku.strip()
        name = name.strip()
        description = description.strip()

        if not sku:
            raise ValueError("SKU is required.")
        if not name:
            raise ValueError("Name is required.")
        if quantity_available < 0:
            raise ValueError("Quantity must be >= 0.")

        other = self._repo.get_by_sku(sku)
        if other and other.id != product.id:
            raise ValueError("SKU already exists on another product.")

        product.sku = sku
        product.name = name
        product.description = description
        product.price = Money(currency="USD", cents=self._parse_price_to_cents(price_str))
        product.quantity_available = quantity_available
        product.is_active = is_active

        self._repo.save(product)
        return product

    def set_stock(self, *, product_id: UUID, quantity_available: int) -> None:
        if quantity_available < 0:
            raise ValueError("Quantity must be >= 0.")
        product = self._repo.get_by_id(product_id)
        if not product:
            raise ValueError("Product not found.")
        product.quantity_available = quantity_available
        self._repo.save(product)

    def toggle_active(self, *, product_id: UUID) -> None:
        product = self._repo.get_by_id(product_id)
        if not product:
            raise ValueError("Product not found.")
        product.is_active = not product.is_active
        self._repo.save(product)

    @staticmethod
    def _parse_price_to_cents(price_str: str) -> int:
        try:
            d = Decimal(price_str.strip()).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            raise ValueError("Price must be a valid number like 19.99")

        if d < 0:
            raise ValueError("Price must be >= 0")

        return int(d * 100)