from __future__ import annotations

from datetime import timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.domain.address import Address
from backend.app.persistence.models import AddressORM


class SqlAlchemyAddressRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, address: Address) -> None:
        row = AddressORM(
            id=str(address.id),
            user_id=str(address.user_id),
            label=address.label,
            recipient_name=address.recipient_name,
            line1=address.line1,
            line2=address.line2,
            city=address.city,
            state=address.state,
            postal_code=address.postal_code,
            country=address.country,
            phone=address.phone,
            is_default=address.is_default,
            is_active=address.is_active,
            created_at=address.created_at,
        )
        self._db.add(row)

    def save(self, address: Address) -> None:
        row = self._db.get(AddressORM, str(address.id))
        if not row:
            self.add(address)
            return

        row.label = address.label
        row.recipient_name = address.recipient_name
        row.line1 = address.line1
        row.line2 = address.line2
        row.city = address.city
        row.state = address.state
        row.postal_code = address.postal_code
        row.country = address.country
        row.phone = address.phone
        row.is_default = address.is_default
        row.is_active = address.is_active

    def get_by_id(self, address_id: UUID) -> Optional[Address]:
        row = self._db.get(AddressORM, str(address_id))
        return self._to_domain(row) if row else None

    def list_active_by_user(self, user_id: UUID) -> List[Address]:
        stmt = (
            select(AddressORM)
            .where(AddressORM.user_id == str(user_id))
            .where(AddressORM.is_active == True)  # noqa: E712
            .order_by(AddressORM.is_default.desc(), AddressORM.created_at.desc())
        )
        rows = self._db.scalars(stmt).all()
        return [self._to_domain(r) for r in rows]

    def get_default(self, user_id: UUID) -> Optional[Address]:
        stmt = (
            select(AddressORM)
            .where(AddressORM.user_id == str(user_id))
            .where(AddressORM.is_active == True)  # noqa: E712
            .where(AddressORM.is_default == True)  # noqa: E712
            .limit(1)
        )
        row = self._db.scalars(stmt).first()
        return self._to_domain(row) if row else None

    def set_default(self, user_id: UUID, address_id: UUID) -> None:
        # unset all
        self._db.execute(
            update(AddressORM)
            .where(AddressORM.user_id == str(user_id))
            .values(is_default=False)
        )
        # set one
        row = self._db.get(AddressORM, str(address_id))
        if row and row.user_id == str(user_id) and row.is_active:
            row.is_default = True

    def deactivate(self, address_id: UUID) -> None:
        row = self._db.get(AddressORM, str(address_id))
        if row:
            row.is_active = False
            row.is_default = False

    @staticmethod
    def _to_domain(row: AddressORM) -> Address:
        created = row.created_at
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        return Address(
            id=UUID(row.id),
            user_id=UUID(row.user_id),
            label=row.label or "",
            recipient_name=row.recipient_name,
            line1=row.line1,
            line2=row.line2 or "",
            city=row.city or "",
            state=row.state or "",
            postal_code=row.postal_code or "",
            country=row.country or "",
            phone=row.phone or "",
            is_default=bool(row.is_default),
            is_active=bool(row.is_active),
            created_at=created,
        )