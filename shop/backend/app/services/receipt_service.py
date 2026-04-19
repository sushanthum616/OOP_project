from __future__ import annotations

from pathlib import Path

from backend.app.domain.orders import Order
from backend.app.domain.payment import Payment


class ReceiptService:
    def __init__(self, base_dir: Path) -> None:
        self._dir = base_dir / "receipts"
        self._dir.mkdir(parents=True, exist_ok=True)

    def generate_receipt_text(self, *, order: Order, payment: Payment, user_email: str) -> str:
        lines = []
        lines.append("MiniShop Receipt")
        lines.append("=" * 40)
        lines.append(f"Order: {order.id}")
        lines.append(f"User: {user_email}")
        lines.append(f"Payment: {payment.status} ({payment.provider} ref: {payment.provider_ref})")
        lines.append(f"Created: {order.created_at.isoformat()}")
        lines.append("-" * 40)

        for ln in order.lines:
            lines.append(f"{ln.name} ({ln.sku})")
            lines.append(f"  {ln.unit_price} x {ln.qty} = {ln.line_total()}")
        lines.append("-" * 40)
        lines.append(f"TOTAL: {order.total}")
        lines.append("")
        lines.append("Shipping To:")
        lines.append(order.shipping_name)
        lines.append(order.shipping_address)
        lines.append("")
        return "\n".join(lines)

    def write_receipt_file(self, *, order: Order, payment: Payment, user_email: str) -> Path:
        txt = self.generate_receipt_text(order=order, payment=payment, user_email=user_email)
        path = self._dir / f"receipt_{order.id}.txt"
        path.write_text(txt, encoding="utf-8")
        return path

    def simulate_email_send(self, *, order: Order, payment: Payment, user_email: str) -> Path:
        path = self.write_receipt_file(order=order, payment=payment, user_email=user_email)
        # "Email simulation" = log to console
        print(f"[MiniShop] Receipt email simulated -> to={user_email} file={path}")
        return path