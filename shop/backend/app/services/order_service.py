from __future__ import annotations

from typing import Dict, List, Tuple
from uuid import UUID

from backend.app.domain.models import Money, User
from backend.app.domain.orders import Order, OrderLine
from backend.app.repositories.order_repo import OrderRepository
from backend.app.repositories.product_repo import ProductRepository
from backend.app.domain.orders import OrderStatus, can_transition

class OrderService:
    def __init__(self, order_repo: OrderRepository, product_repo: ProductRepository) -> None:
        self._order_repo = order_repo
        self._product_repo = product_repo

    def place_order(
        self,
        *,
        user: User,
        cart_items: Dict[str, int],
        shipping_name: str,
        shipping_address: str,
    ) -> Order:
        if not cart_items:
            raise ValueError("Your cart is empty.")

        pending: List[Tuple[UUID, int]] = []
        lines: List[OrderLine] = []
        total = Money(currency="USD", cents=0)

        # 1) Validate and compute totals (no stock mutation yet)
        for pid_str, qty in cart_items.items():
            try:
                qty_int = int(qty)
            except Exception:
                continue
            if qty_int <= 0:
                continue

            try:
                pid = UUID(pid_str)
            except Exception:
                continue

            product = self._product_repo.get_by_id(pid)
            if not product or not product.is_active:
                raise ValueError("A product in your cart is no longer available.")

            if qty_int > product.quantity_available:
                raise ValueError(f"Not enough stock for '{product.name}'. Available: {product.quantity_available}")

            pending.append((pid, qty_int))
            lines.append(
                OrderLine(
                    product_id=product.id,
                    sku=product.sku,
                    name=product.name,
                    unit_price=product.price,
                    qty=qty_int,
                )
            )
            total = total + product.price.multiply(qty_int)

        if not lines:
            raise ValueError("Your cart is empty.")

        # 2) Apply stock decrease after all validations pass
        for pid, qty_int in pending:
            product = self._product_repo.get_by_id(pid)
            if not product:
                raise ValueError("A product in your cart is missing.")
            if qty_int > product.quantity_available:
                raise ValueError(f"Stock changed for '{product.name}'. Try again.")
            product.quantity_available -= qty_int
            self._product_repo.save(product)

        # 3) Create + save order
        order = Order.create(
            user_id=user.id,
            lines=lines,
            total=total,
            shipping_name=shipping_name,
            shipping_address=shipping_address,
        )
        self._order_repo.add(order)
        return order

    def list_orders_for_user(self, user_id: UUID) -> List[Order]:
        return self._order_repo.list_by_user(user_id)

    def get_order_for_user(self, *, user_id: UUID, order_id: UUID) -> Order | None:
        order = self._order_repo.get_by_id(order_id)
        if not order or order.user_id != user_id:
            return None
        return order
    
    def get_order(self, order_id: UUID) -> Order | None:
         return self._order_repo.get_by_id(order_id)

    def list_all_orders(self) -> List[Order]:
        return self._order_repo.list_all()

    def cancel_order_for_user(self, *, user: User, order_id: UUID) -> Order:
        order = self.get_order_for_user(user_id=user.id, order_id=order_id)
        if not order:
            raise ValueError("Order not found.")
        return self._cancel_and_restock(order)

    def cancel_order_admin(self, *, order_id: UUID) -> Order:
        order = self._order_repo.get_by_id(order_id)
        if not order:
            raise ValueError("Order not found.")
        return self._cancel_and_restock(order)

    def update_status_admin(self, *, order_id: UUID, new_status: str) -> Order:
        new_status = (new_status or "").strip().upper()
        if new_status not in OrderStatus.ALL:
            raise ValueError("Invalid status.")

        order = self._order_repo.get_by_id(order_id)
        if not order:
            raise ValueError("Order not found.")

        current = order.status

        # If admin chooses CANCELLED, do full cancel + restock
        if new_status == OrderStatus.CANCELLED:
            return self.cancel_order_admin(order_id=order_id)

        if not can_transition(current, new_status):
            raise ValueError(f"Cannot change status from {current} to {new_status}.")

        self._order_repo.set_status(order_id, new_status)
        order.status = new_status
        return order

    def _cancel_and_restock(self, order: Order) -> Order:
        if order.status == OrderStatus.CANCELLED:
            return order

        if order.status not in OrderStatus.CANCELLABLE:
            raise ValueError(f"Order cannot be cancelled when status is {order.status}.")

        # Restock items
        for ln in order.lines:
            product = self._product_repo.get_by_id(ln.product_id)
            if product:
                product.quantity_available += ln.qty
                self._product_repo.save(product)

        # Update order status
        self._order_repo.set_status(order.id, OrderStatus.CANCELLED)
        order.status = OrderStatus.CANCELLED
        return order