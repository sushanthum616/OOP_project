from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.domain.models import Money
from backend.app.domain.payment import Payment
from backend.app.persistence.models import PaymentORM


class SqlAlchemyPaymentRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, payment: Payment) -> None:
        row = PaymentORM(
            id=str(payment.id),
            order_id=str(payment.order_id),
            user_id=str(payment.user_id),
            amount_currency=payment.amount.currency,
            amount_cents=payment.amount.cents,
            status=payment.status,
            provider=payment.provider,
            provider_ref=payment.provider_ref,
            last_error=payment.last_error,
            created_at=payment.created_at,
            updated_at=payment.updated_at,
        )
        self._db.add(row)

    def get_by_order(self, order_id: UUID) -> Optional[Payment]:
        stmt = select(PaymentORM).where(PaymentORM.order_id == str(order_id)).limit(1)
        row = self._db.scalars(stmt).first()
        return self._to_domain(row) if row else None

    def set_status(self, payment_id: UUID, status: str, *, last_error: str = "") -> None:
        row = self._db.get(PaymentORM, str(payment_id))
        if not row:
            return
        row.status = status
        row.last_error = last_error or ""
        row.updated_at = datetime.now(timezone.utc)

    @staticmethod
    def _to_domain(row: PaymentORM) -> Payment:
        created = row.created_at
        updated = row.updated_at
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if updated and updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)

        return Payment(
            id=UUID(row.id),
            order_id=UUID(row.order_id),
            user_id=UUID(row.user_id),
            amount=Money(currency=row.amount_currency, cents=row.amount_cents),
            status=row.status,
            provider=row.provider,
            provider_ref=row.provider_ref or "",
            last_error=row.last_error or "",
            created_at=created,
            updated_at=updated,
        )