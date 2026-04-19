from __future__ import annotations

from typing import Optional, Protocol
from uuid import UUID

from backend.app.domain.payment import Payment


class PaymentRepository(Protocol):
    def add(self, payment: Payment) -> None:
        ...

    def get_by_order(self, order_id: UUID) -> Optional[Payment]:
        ...

    def set_status(self, payment_id: UUID, status: str, *, last_error: str = "") -> None:
        ...