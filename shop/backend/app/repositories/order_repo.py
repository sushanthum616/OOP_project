from __future__ import annotations

from typing import Dict, List, Optional, Protocol
from uuid import UUID

from backend.app.domain.orders import Order


class OrderRepository(Protocol):
    def add(self, order: Order) -> None:
        ...

    def get_by_id(self, order_id: UUID) -> Optional[Order]:
        ...

    def list_by_user(self, user_id: UUID) -> List[Order]:
        ...

    def list_all(self) -> List[Order]:
        ...

    def set_status(self, order_id: UUID, new_status: str) -> None:
        ...

    def user_has_purchased_product(self, user_id: UUID, product_id: UUID) -> bool:
        ...

class InMemoryOrderRepository:
    def __init__(self) -> None:
        self._orders: Dict[UUID, Order] = {}

    def add(self, order: Order) -> None:
        self._orders[order.id] = order

    def get_by_id(self, order_id: UUID) -> Optional[Order]:
        return self._orders.get(order_id)

    def list_by_user(self, user_id: UUID) -> List[Order]:
        items = [o for o in self._orders.values() if o.user_id == user_id]
        items.sort(key=lambda o: o.created_at, reverse=True)
        return items
    
    def list_all(self) -> List[Order]:
        items = list(self._orders.values())
        items.sort(key=lambda o: o.created_at, reverse=True)
        return items

    def set_status(self, order_id: UUID, new_status: str) -> None:
        order = self._orders.get(order_id)
        if order:
            order.status = new_status

    def user_has_purchased_product(self, user_id: UUID, product_id: UUID) -> bool:
        for o in self._orders.values():
            if o.user_id != user_id:
                continue
            if o.status == "CANCELLED":
                continue
            for ln in o.lines:
                if ln.product_id == product_id:
                    return True
        return False