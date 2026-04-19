from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass
class Address:
    id: UUID
    user_id: UUID
    label: str
    recipient_name: str
    line1: str
    line2: str
    city: str
    state: str
    postal_code: str
    country: str
    phone: str
    is_default: bool = False
    is_active: bool = True
    created_at: datetime | None = None

    @staticmethod
    def create(
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
        is_default: bool = False,
    ) -> "Address":
        return Address(
            id=uuid4(),
            user_id=user_id,
            label=label.strip(),
            recipient_name=recipient_name.strip(),
            line1=line1.strip(),
            line2=line2.strip(),
            city=city.strip(),
            state=state.strip(),
            postal_code=postal_code.strip(),
            country=country.strip(),
            phone=phone.strip(),
            is_default=is_default,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )

    def format_multiline(self) -> str:
        lines: list[str] = []
        if self.line1:
            lines.append(self.line1)
        if self.line2:
            lines.append(self.line2)

        city_state_zip = " ".join([self.state, self.postal_code]).strip()
        if self.city and city_state_zip:
            lines.append(f"{self.city}, {city_state_zip}")
        elif self.city:
            lines.append(self.city)
        elif city_state_zip:
            lines.append(city_state_zip)

        if self.country:
            lines.append(self.country)

        if self.phone:
            lines.append(f"Phone: {self.phone}")

        return "\n".join([x for x in lines if x.strip()])

    def to_dict(self) -> dict:
        created = self.created_at
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "label": self.label,
            "recipient_name": self.recipient_name,
            "line1": self.line1,
            "line2": self.line2,
            "city": self.city,
            "state": self.state,
            "postal_code": self.postal_code,
            "country": self.country,
            "phone": self.phone,
            "is_default": self.is_default,
            "is_active": self.is_active,
            "display": self.format_multiline(),
        }