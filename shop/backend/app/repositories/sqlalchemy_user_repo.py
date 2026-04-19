from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.domain.models import User
from backend.app.persistence.models import UserORM


class SqlAlchemyUserRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, user: User) -> None:
        row = UserORM(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            password_hash=user.password_hash,
            is_active=user.is_active,
            is_admin=user.is_admin,
        )
        self._db.add(row)

    def get_by_id(self, user_id: UUID) -> Optional[User]:
        row = self._db.get(UserORM, str(user_id))
        return self._to_domain(row) if row else None

    def get_by_email(self, email: str) -> Optional[User]:
        email_norm = email.strip().lower()
        stmt = select(UserORM).where(UserORM.email == email_norm)
        row = self._db.scalars(stmt).first()
        return self._to_domain(row) if row else None

    @staticmethod
    def _to_domain(row: UserORM) -> User:
        return User(
            id=UUID(row.id),
            email=row.email,
            full_name=row.full_name,
            password_hash=row.password_hash,
            is_active=row.is_active,
            is_admin=getattr(row, "is_admin", False),
        )