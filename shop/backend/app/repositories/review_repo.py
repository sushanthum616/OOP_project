from __future__ import annotations

from typing import List, Optional, Protocol
from uuid import UUID

from backend.app.domain.review import Review


class ReviewRepository(Protocol):
    def add(self, review: Review) -> None:
        ...

    def save(self, review: Review) -> None:
        ...

    def get_by_product_and_user(self, product_id: UUID, user_id: UUID) -> Optional[Review]:
        ...

    def list_active_for_product(self, product_id: UUID, *, limit: int, offset: int) -> List[Review]:
        ...

    def stats_for_product(self, product_id: UUID) -> tuple[int, float | None]:
        ...