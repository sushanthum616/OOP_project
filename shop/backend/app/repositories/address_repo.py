from __future__ import annotations

from typing import List, Optional, Protocol
from uuid import UUID

from backend.app.domain.address import Address


class AddressRepository(Protocol):
    def add(self, address: Address) -> None:
        ...

    def save(self, address: Address) -> None:
        ...

    def get_by_id(self, address_id: UUID) -> Optional[Address]:
        ...

    def list_active_by_user(self, user_id: UUID) -> List[Address]:
        ...

    def get_default(self, user_id: UUID) -> Optional[Address]:
        ...

    def set_default(self, user_id: UUID, address_id: UUID) -> None:
        ...

    def deactivate(self, address_id: UUID) -> None:
        ...