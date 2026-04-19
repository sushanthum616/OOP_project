from __future__ import annotations

from uuid import UUID

from backend.app.domain.address import Address
from backend.app.repositories.address_repo import AddressRepository


class AddressService:
    def __init__(self, repo: AddressRepository) -> None:
        self._repo = repo

    def list_addresses(self, user_id: UUID) -> list[Address]:
        return self._repo.list_active_by_user(user_id)

    def get_default_address(self, user_id: UUID) -> Address | None:
        return self._repo.get_default(user_id)

    def get_address_for_user(self, user_id: UUID, address_id: UUID) -> Address | None:
        a = self._repo.get_by_id(address_id)
        if not a or not a.is_active or a.user_id != user_id:
            return None
        return a

    def create_address(
        self,
        *,
        user_id: UUID,
        label: str,
        recipient_name: str,
        line1: str,
        line2: str = "",
        city: str = "",
        state: str = "",
        postal_code: str = "",
        country: str = "",
        phone: str = "",
        make_default: bool = False,
    ) -> Address:
        if not recipient_name.strip():
            raise ValueError("Recipient name is required.")
        if not line1.strip():
            raise ValueError("Address line 1 is required.")
        if not city.strip():
            raise ValueError("City is required.")

        existing_default = self._repo.get_default(user_id)

        addr = Address.create(
            user_id=user_id,
            label=label,
            recipient_name=recipient_name,
            line1=line1,
            line2=line2,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
            phone=phone,
            is_default=False,
        )
        self._repo.add(addr)

        # If user has no default, make this default automatically
        if make_default or existing_default is None:
            self._repo.set_default(user_id, addr.id)
            addr.is_default = True

        return addr

    def update_address(
        self,
        *,
        user_id: UUID,
        address_id: UUID,
        label: str,
        recipient_name: str,
        line1: str,
        line2: str = "",
        city: str = "",
        state: str = "",
        postal_code: str = "",
        country: str = "",
        phone: str = "",
        make_default: bool = False,
    ) -> Address:
        addr = self.get_address_for_user(user_id, address_id)
        if not addr:
            raise ValueError("Address not found.")

        if not recipient_name.strip():
            raise ValueError("Recipient name is required.")
        if not line1.strip():
            raise ValueError("Address line 1 is required.")
        if not city.strip():
            raise ValueError("City is required.")

        addr.label = label.strip()
        addr.recipient_name = recipient_name.strip()
        addr.line1 = line1.strip()
        addr.line2 = line2.strip()
        addr.city = city.strip()
        addr.state = state.strip()
        addr.postal_code = postal_code.strip()
        addr.country = country.strip()
        addr.phone = phone.strip()

        self._repo.save(addr)

        if make_default:
            self._repo.set_default(user_id, addr.id)
            addr.is_default = True

        return addr

    def delete_address(self, *, user_id: UUID, address_id: UUID) -> None:
        addr = self.get_address_for_user(user_id, address_id)
        if not addr:
            raise ValueError("Address not found.")
        self._repo.deactivate(addr.id)

    def set_default(self, *, user_id: UUID, address_id: UUID) -> None:
        addr = self.get_address_for_user(user_id, address_id)
        if not addr:
            raise ValueError("Address not found.")
        self._repo.set_default(user_id, addr.id)