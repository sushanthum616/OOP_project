from __future__ import annotations

from datetime import timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.domain.review import Review
from backend.app.persistence.models import ReviewORM


class SqlAlchemyReviewRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, review: Review) -> None:
        row = ReviewORM(
            id=str(review.id),
            product_id=str(review.product_id),
            user_id=str(review.user_id),
            rating=review.rating,
            title=review.title,
            body=review.body,
            is_active=review.is_active,
            created_at=review.created_at,
        )
        self._db.add(row)

    def save(self, review: Review) -> None:
        row = self._db.get(ReviewORM, str(review.id))
        if not row:
            self.add(review)
            return
        row.rating = review.rating
        row.title = review.title
        row.body = review.body
        row.is_active = review.is_active

    def get_by_product_and_user(self, product_id: UUID, user_id: UUID) -> Optional[Review]:
        stmt = (
            select(ReviewORM)
            .where(ReviewORM.product_id == str(product_id))
            .where(ReviewORM.user_id == str(user_id))
            .limit(1)
        )
        row = self._db.scalars(stmt).first()
        return self._to_domain(row) if row else None

    def list_active_for_product(self, product_id: UUID, *, limit: int, offset: int) -> List[Review]:
        stmt = (
            select(ReviewORM)
            .where(ReviewORM.product_id == str(product_id))
            .where(ReviewORM.is_active == True)  # noqa: E712
            .order_by(ReviewORM.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = self._db.scalars(stmt).all()
        return [self._to_domain(r) for r in rows]

    def stats_for_product(self, product_id: UUID) -> tuple[int, float | None]:
        stmt = (
            select(func.count(ReviewORM.id), func.avg(ReviewORM.rating))
            .where(ReviewORM.product_id == str(product_id))
            .where(ReviewORM.is_active == True)  # noqa: E712
        )
        count, avg = self._db.execute(stmt).one()
        count_i = int(count or 0)
        avg_f = float(avg) if avg is not None else None
        return count_i, avg_f

    @staticmethod
    def _to_domain(row: ReviewORM) -> Review:
        created = row.created_at
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        return Review(
            id=UUID(row.id),
            product_id=UUID(row.product_id),
            user_id=UUID(row.user_id),
            rating=row.rating,
            title=row.title or "",
            body=row.body or "",
            created_at=created,
            is_active=bool(row.is_active),
        )