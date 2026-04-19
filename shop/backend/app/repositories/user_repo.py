from __future__ import annotations

from typing import Dict, Optional, Protocol
from uuid import UUID

from backend.app.domain.models import User


class UserRepository(Protocol):
    def add(self, user: User) -> None:
        ...

    def get_by_id(self, user_id: UUID) -> Optional[User]:
        ...

    def get_by_email(self, email: str) -> Optional[User]:
        ...


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._users_by_id: Dict[UUID, User] = {}
        self._users_by_email: Dict[str, User] = {}

    def add(self, user: User) -> None:
        self._users_by_id[user.id] = user
        self._users_by_email[user.email] = user

    def get_by_id(self, user_id: UUID) -> Optional[User]:
        return self._users_by_id.get(user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        return self._users_by_email.get(email.strip().lower())