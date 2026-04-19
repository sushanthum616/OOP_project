from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List
from uuid import UUID, uuid4

from backend.app.domain.models import Money


class OrderStatus:
    PLACED = "PLACED"
    PROCESSING = "PROCESSING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"

    ALL = [PLACED, PROCESSING, SHIPPED, DELIVERED, CANCELLED]
    CANCELLABLE = {PLACED, PROCESSING}


ALLOWED_TRANSITIONS = {
    OrderStatus.PLACED: {OrderStatus.PROCESSING, OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.PROCESSING: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}


def can_transition(current: str, new: str) -> bool:
    if current == new:
        return True
    return new in ALLOWED_TRANSITIONS.get(current, set())

@dataclass(frozen=True)
class OrderLine:
    product_id: UUID
    sku: str
    name: str
    unit_price: Money
    qty: int

    def line_total(self) -> Money:
        return self.unit_price.multiply(self.qty)

    def to_dict(self) -> dict:
        return {
            "product_id": str(self.product_id),
            "sku": self.sku,
            "name": self.name,
            "unit_price": {
                "currency": self.unit_price.currency,
                "cents": self.unit_price.cents,
                "display": str(self.unit_price),
            },
            "qty": self.qty,
            "line_total": {
                "currency": self.line_total().currency,
                "cents": self.line_total().cents,
                "display": str(self.line_total()),
            },
        }


@dataclass
class Order:
    id: UUID
    user_id: UUID
    lines: List[OrderLine]
    total: Money
    created_at: datetime
    status: str
    shipping_name: str
    shipping_address: str

    @staticmethod
    def create(
        *,
        user_id: UUID,
        lines: List[OrderLine],
        total: Money,
        shipping_name: str,
        shipping_address: str,
        status: str = "PLACED",
    ) -> "Order":
        return Order(
            id=uuid4(),
            user_id=user_id,
            lines=lines,
            total=total,
            created_at=datetime.now(timezone.utc),
            status=status,
            shipping_name=shipping_name.strip(),
            shipping_address=shipping_address.strip(),
        )

    def to_dict(self) -> dict:
        created_display = self.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return {
            "id": str(self.id),
            "id_short": str(self.id).split("-")[0],
            "user_id": str(self.user_id),
            "created_at": self.created_at.isoformat(),
            "created_at_display": created_display,
            "status": self.status,
            "shipping_name": self.shipping_name,
            "shipping_address": self.shipping_address,
            "total": {
                "currency": self.total.currency,
                "cents": self.total.cents,
                "display": str(self.total),
            },
            "lines": [ln.to_dict() for ln in self.lines],
        }