from __future__ import annotations

from backend.app.domain.models import User
from backend.app.domain.security import hash_password, verify_password
from backend.app.repositories.user_repo import UserRepository


class AuthService:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    def register(self, *, email: str, full_name: str, password: str, is_admin: bool = False) -> User:
        email_norm = email.strip().lower()
        if self._user_repo.get_by_email(email_norm):
            raise ValueError("Email already registered")

        pw_hash = hash_password(password)
        user = User.create(email=email_norm, full_name=full_name, password_hash=pw_hash, is_admin=is_admin)
        self._user_repo.add(user)
        return user

    def authenticate(self, *, email: str, password: str) -> User | None:
        user = self._user_repo.get_by_email(email)
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user