from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from backend.app.domain.models import Money
from backend.app.domain.payment import Payment, PaymentStatus
from backend.app.repositories.payment_repo import PaymentRepository
from backend.app.logger import logger

class PaymentService:
    def __init__(self, repo: PaymentRepository) -> None:
        self._repo = repo

    def get_or_create(self, *, order_id: UUID, user_id: UUID, amount: Money) -> Payment:
        existing = self._repo.get_by_order(order_id)
        if existing:
            return existing
        payment = Payment.create(order_id=order_id, user_id=user_id, amount=amount)
        self._repo.add(payment)
        return payment

    def mark_paid(self, *, order_id: UUID) -> Payment:
        payment = self._repo.get_by_order(order_id)
        if not payment:
            raise ValueError("Payment not found.")
        if payment.status == PaymentStatus.PAID:
            return payment

        self._repo.set_status(payment.id, PaymentStatus.PAID, last_error="")
        payment.status = PaymentStatus.PAID
        payment.last_error = ""
        payment.updated_at = datetime.now(timezone.utc)
        return payment

    def mark_failed(self, *, order_id: UUID, message: str = "Mock payment failed.") -> Payment:
        payment = self._repo.get_by_order(order_id)
        if not payment:
            raise ValueError("Payment not found.")

        self._repo.set_status(payment.id, PaymentStatus.FAILED, last_error=message)
        payment.status = PaymentStatus.FAILED
        payment.last_error = message
        payment.updated_at = datetime.now(timezone.utc)
        return payment

    def refund_if_paid(self, *, order_id: UUID) -> Payment | None:
        payment = self._repo.get_by_order(order_id)
        if not payment:
            return None
        if payment.status != PaymentStatus.PAID:
            return payment

        self._repo.set_status(payment.id, PaymentStatus.REFUNDED, last_error="")
        payment.status = PaymentStatus.REFUNDED
        payment.last_error = ""
        payment.updated_at = datetime.now(timezone.utc)
        return payment