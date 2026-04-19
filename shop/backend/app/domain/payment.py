from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from backend.app.domain.models import Money


class PaymentStatus:
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"

    ALL = [PENDING, PAID, FAILED, REFUNDED]


@dataclass
class Payment:
    id: UUID
    order_id: UUID
    user_id: UUID
    amount: Money
    status: str
    provider: str
    provider_ref: str
    last_error: str
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def create(*, order_id: UUID, user_id: UUID, amount: Money) -> "Payment":
        now = datetime.now(timezone.utc)
        return Payment(
            id=uuid4(),
            order_id=order_id,
            user_id=user_id,
            amount=amount,
            status=PaymentStatus.PENDING,
            provider="MOCK",
            provider_ref=str(uuid4())[:12],
            last_error="",
            created_at=now,
            updated_at=now,
        )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "order_id": str(self.order_id),
            "user_id": str(self.user_id),
            "amount": {
                "currency": self.amount.currency,
                "cents": self.amount.cents,
                "display": str(self.amount),
            },
            "status": self.status,
            "provider": self.provider,
            "provider_ref": self.provider_ref,
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }