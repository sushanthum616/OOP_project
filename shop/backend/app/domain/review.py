from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass
class Review:
    id: UUID
    product_id: UUID
    user_id: UUID
    rating: int
    title: str
    body: str
    created_at: datetime
    is_active: bool = True

    @staticmethod
    def create(
        *,
        product_id: UUID,
        user_id: UUID,
        rating: int,
        title: str = "",
        body: str = "",
    ) -> "Review":
        return Review(
            id=uuid4(),
            product_id=product_id,
            user_id=user_id,
            rating=rating,
            title=title.strip(),
            body=body.strip(),
            created_at=datetime.now(timezone.utc),
            is_active=True,
        )

    def to_dict(self) -> dict:
        created = self.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        return {
            "id": str(self.id),
            "product_id": str(self.product_id),
            "user_id": str(self.user_id),
            "rating": self.rating,
            "title": self.title,
            "body": self.body,
            "created_at": created.isoformat(),
            "created_at_display": created.strftime("%Y-%m-%d %H:%M UTC"),
            "is_active": self.is_active,
        }