from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
from uuid import UUID

from backend.app.domain.models import Money
from backend.app.repositories.product_repo import ProductRepository


@dataclass(frozen=True)
class CartLine:
    product_id: str
    name: str
    unit_price_display: str
    qty: int
    available: int
    line_total_display: str


class CartService:
    SESSION_KEY = "cart"

    def __init__(self, product_repo: ProductRepository) -> None:
        self._product_repo = product_repo

    def _get_cart_dict(self, session: Dict[str, Any]) -> Dict[str, int]:
        cart = session.get(self.SESSION_KEY)
        if not isinstance(cart, dict):
            cart = {}
            session[self.SESSION_KEY] = cart
        # ensure values are ints
        clean: Dict[str, int] = {}
        for k, v in cart.items():
            try:
                clean[str(k)] = int(v)
            except Exception:
                pass
        session[self.SESSION_KEY] = clean
        return clean

    def count_items(self, session: Dict[str, Any]) -> int:
        cart = self._get_cart_dict(session)
        return sum(cart.values())

    def add(self, session: Dict[str, Any], product_id: UUID, qty: int = 1) -> None:
        if qty <= 0:
            return

        product = self._product_repo.get_by_id(product_id)
        if not product or not product.is_active:
            raise ValueError("Product not available")

        cart = self._get_cart_dict(session)
        key = str(product_id)
        current = cart.get(key, 0)

        if current + qty > product.quantity_available:
            raise ValueError(f"Only {product.quantity_available} left in stock for '{product.name}'")

        cart[key] = current + qty
        session[self.SESSION_KEY] = cart

    def remove(self, session: Dict[str, Any], product_id: UUID) -> None:
        cart = self._get_cart_dict(session)
        key = str(product_id)
        if key in cart:
            del cart[key]
        session[self.SESSION_KEY] = cart

    def clear(self, session: Dict[str, Any]) -> None:
        session[self.SESSION_KEY] = {}

    def build_view(self, session: Dict[str, Any]) -> tuple[List[CartLine], str]:
        cart = self._get_cart_dict(session)

        lines: List[CartLine] = []
        total = Money(currency="USD", cents=0)

        for pid_str, qty in cart.items():
            try:
                pid = UUID(pid_str)
            except Exception:
                continue

            product = self._product_repo.get_by_id(pid)
            if not product or not product.is_active:
                continue

            line_total = product.price.multiply(qty)
            total = total + line_total

            lines.append(
                CartLine(
                    product_id=str(product.id),
                    name=product.name,
                    unit_price_display=str(product.price),
                    qty=qty,
                    available=product.quantity_available,
                    line_total_display=str(line_total),
                )
            )

        return lines, str(total)
    def items(self, session: Dict[str, Any]) -> Dict[str, int]:
        # returns a safe copy of the cart dict {product_id_str: qty}
        return dict(self._get_cart_dict(session))
    
    def set_qty(self, session: Dict[str, Any], product_id: UUID, qty: int) -> None:
        cart = self._get_cart_dict(session)
        key = str(product_id)

        if qty <= 0:
            if key in cart:
                del cart[key]
            session[self.SESSION_KEY] = cart
            return

        product = self._product_repo.get_by_id(product_id)
        if not product or not product.is_active:
            raise ValueError("Product not available")

        if qty > product.quantity_available:
            raise ValueError(f"Only {product.quantity_available} left in stock for '{product.name}'")

        cart[key] = qty
        session[self.SESSION_KEY] = cart