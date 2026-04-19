from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True)
class Money:
    currency: str
    cents: int

    @staticmethod
    def from_dollars(amount: float, currency: str = "USD") -> "Money":
        cents = int(round(amount * 100))
        return Money(currency=currency, cents=cents)

    def multiply(self, qty: int) -> "Money":
        if qty < 0:
            raise ValueError("qty must be >= 0")
        return Money(currency=self.currency, cents=self.cents * qty)

    def __add__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError("Cannot add Money with different currencies")
        return Money(currency=self.currency, cents=self.cents + other.cents)

    def __str__(self) -> str:
        return f"{self.currency} {self.cents / 100:.2f}"


@dataclass
class Product:
    id: UUID
    sku: str
    name: str
    description: str
    price: Money
    quantity_available: int
    is_active: bool = True

    @staticmethod
    def create(
        sku: str,
        name: str,
        description: str,
        price: Money,
        quantity_available: int,
        *,
        is_active: bool = True,
    ) -> "Product":
        return Product(
            id=uuid4(),
            sku=sku,
            name=name,
            description=description,
            price=price,
            quantity_available=quantity_available,
            is_active=is_active,
        )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "sku": self.sku,
            "name": self.name,
            "description": self.description,
            "price": {
                "currency": self.price.currency,
                "cents": self.price.cents,
                "display": str(self.price),
            },
            "quantity_available": self.quantity_available,
            "is_active": self.is_active,
        }


@dataclass
class User:
    id: UUID
    email: str
    full_name: str
    password_hash: str
    is_active: bool = True
    is_admin: bool = False

    @staticmethod
    def create(email: str, full_name: str, password_hash: str, *, is_admin: bool = False) -> "User":
        email_norm = email.strip().lower()
        if not email_norm:
            raise ValueError("Email cannot be empty")
        if not full_name.strip():
            raise ValueError("Full name cannot be empty")
        return User(
            id=uuid4(),
            email=email_norm,
            full_name=full_name.strip(),
            password_hash=password_hash,
            is_active=True,
            is_admin=is_admin,
        )

    def to_public_dict(self) -> dict:
        return {
            "id": str(self.id),
            "email": self.email,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "is_admin": self.is_admin,
        }