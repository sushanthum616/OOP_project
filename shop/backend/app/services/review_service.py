from __future__ import annotations

from uuid import UUID

from backend.app.domain.models import User
from backend.app.domain.review import Review
from backend.app.repositories.order_repo import OrderRepository
from backend.app.repositories.review_repo import ReviewRepository
from backend.app.repositories.user_repo import UserRepository


class ReviewService:
    def __init__(self, review_repo: ReviewRepository, order_repo: OrderRepository, user_repo: UserRepository) -> None:
        self._review_repo = review_repo
        self._order_repo = order_repo
        self._user_repo = user_repo

    def user_can_review(self, *, user_id: UUID, product_id: UUID) -> bool:
        return self._order_repo.user_has_purchased_product(user_id, product_id)

    def get_user_review(self, *, user_id: UUID, product_id: UUID) -> Review | None:
        return self._review_repo.get_by_product_and_user(product_id, user_id)

    def get_stats(self, *, product_id: UUID) -> tuple[int, float | None]:
        return self._review_repo.stats_for_product(product_id)

    def list_reviews(self, *, product_id: UUID, limit: int = 20, offset: int = 0) -> list[dict]:
        reviews = self._review_repo.list_active_for_product(product_id, limit=limit, offset=offset)

        view: list[dict] = []
        for r in reviews:
            d = r.to_dict()
            u = self._user_repo.get_by_id(r.user_id)
            d["author_name"] = u.full_name if u else "Unknown"
            d["verified_purchase"] = True  # because we only allow verified purchasers
            view.append(d)

        return view

    def create_or_update_review(
        self,
        *,
        user: User,
        product_id: UUID,
        rating: int,
        title: str = "",
        body: str = "",
    ) -> Review:
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5.")

        title = (title or "").strip()
        body = (body or "").strip()

        if len(title) > 120:
            raise ValueError("Title is too long (max 120 characters).")
        if len(body) > 2000:
            raise ValueError("Review is too long (max 2000 characters).")

        if not self.user_can_review(user_id=user.id, product_id=product_id):
            raise ValueError("Only verified purchasers can review this product.")

        existing = self._review_repo.get_by_product_and_user(product_id, user.id)
        if existing:
            existing.rating = rating
            existing.title = title
            existing.body = body
            existing.is_active = True
            self._review_repo.save(existing)
            return existing

        review = Review.create(
            product_id=product_id,
            user_id=user.id,
            rating=rating,
            title=title,
            body=body,
        )
        self._review_repo.add(review)
        return review