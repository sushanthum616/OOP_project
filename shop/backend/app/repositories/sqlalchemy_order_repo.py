from __future__ import annotations

from datetime import timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.app.domain.models import Money
from backend.app.domain.orders import Order, OrderLine
from backend.app.persistence.models import OrderLineORM, OrderORM


class SqlAlchemyOrderRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, order: Order) -> None:
        order_row = OrderORM(
            id=str(order.id),
            user_id=str(order.user_id),
            total_currency=order.total.currency,
            total_cents=order.total.cents,
            created_at=order.created_at,
            status=order.status,
            shipping_name=order.shipping_name,
            shipping_address=order.shipping_address,
        )
        self._db.add(order_row)

        for ln in order.lines:
            line_row = OrderLineORM(
                order_id=str(order.id),
                product_id=str(ln.product_id),
                sku=ln.sku,
                name=ln.name,
                unit_price_currency=ln.unit_price.currency,
                unit_price_cents=ln.unit_price.cents,
                qty=ln.qty,
            )
            self._db.add(line_row)

    def get_by_id(self, order_id: UUID) -> Optional[Order]:
        row = self._db.get(OrderORM, str(order_id))
        return self._to_domain(row) if row else None

    def list_by_user(self, user_id: UUID) -> List[Order]:
        stmt = (
            select(OrderORM)
            .where(OrderORM.user_id == str(user_id))
            .order_by(OrderORM.created_at.desc())
        )
        rows = self._db.scalars(stmt).all()
        return [self._to_domain(r) for r in rows]

    @staticmethod
    def _to_domain(row: OrderORM) -> Order:
        # SQLite often returns naive datetimes; treat as UTC
        created = row.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        lines: List[OrderLine] = []
        for ln in row.lines:
            lines.append(
                OrderLine(
                    product_id=UUID(ln.product_id),
                    sku=ln.sku,
                    name=ln.name,
                    unit_price=Money(currency=ln.unit_price_currency, cents=ln.unit_price_cents),
                    qty=ln.qty,
                )
            )

        total = Money(currency=row.total_currency, cents=row.total_cents)

        return Order(
            id=UUID(row.id),
            user_id=UUID(row.user_id),
            lines=lines,
            total=total,
            created_at=created,
            status=row.status,
            shipping_name=row.shipping_name,
            shipping_address=row.shipping_address,
        )
    
    def list_all(self) -> List[Order]:
        stmt = select(OrderORM).order_by(OrderORM.created_at.desc())
        rows = self._db.scalars(stmt).all()
        return [self._to_domain(r) for r in rows]

    def set_status(self, order_id: UUID, new_status: str) -> None:
        row = self._db.get(OrderORM, str(order_id))
        if not row:
            return
        row.status = new_status

    def user_has_purchased_product(self, user_id: UUID, product_id: UUID) -> bool:
        stmt = (
            select(func.count(OrderLineORM.id))
            .select_from(OrderLineORM)
            .join(OrderORM, OrderLineORM.order_id == OrderORM.id)
            .where(OrderORM.user_id == str(user_id))
            .where(OrderORM.status != "CANCELLED")
            .where(OrderLineORM.product_id == str(product_id))
        )
        count = self._db.execute(stmt).scalar_one()
        return (count or 0) > 0