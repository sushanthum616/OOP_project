from pathlib import Path
from uuid import uuid4


def _register(client, email=None, password="Pass123!", full_name="Test User"):
    email = email or f"user_{uuid4().hex[:8]}@example.com"
    r = client.post(
        "/register",
        data={"full_name": full_name, "email": email, "password": password},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    return email, password


def test_checkout_payment_receipt_flow(client):
    # Register (auto-logs-in)
    email, password = _register(client)

    # Get products (Day 8 API envelope: items/meta)
    resp = client.get("/api/products")
    assert resp.status_code == 200
    data = resp.json()
    products = data["items"]
    assert len(products) > 0
    product_id = products[0]["id"]

    # Add to cart
    r = client.post(
        f"/cart/add/{product_id}",
        data={"qty": 1, "next": "/cart"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    # Checkout page should load
    r = client.get("/checkout")
    assert r.status_code == 200

    # Submit checkout -> should redirect to /pay/{order_id}
    r = client.post(
        "/checkout",
        data={
            "shipping_name": "Test User",
            "line1": "123 Test Street",
            "line2": "",
            "city": "Testville",
            "state": "",
            "postal_code": "",
            "country": "USA",
            "phone": "",
            "save_address": "",  # unchecked
            "label": "",
            "make_default": "",  # unchecked
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    location = r.headers.get("location", "")
    assert location.startswith("/pay/")
    order_id = location.split("/pay/")[1]

    # Payment page loads
    r = client.get(f"/pay/{order_id}")
    assert r.status_code == 200

    # Simulate success -> should redirect to receipt
    r = client.post(f"/pay/{order_id}/success", follow_redirects=False)
    assert r.status_code in (302, 303)
    receipt_loc = r.headers.get("location", "")
    assert receipt_loc.endswith(f"/orders/{order_id}/receipt") or receipt_loc == f"/orders/{order_id}/receipt"

    # Receipt page loads
    r = client.get(f"/orders/{order_id}/receipt")
    assert r.status_code == 200

    # Back to order should load (this checks your earlier fix: payment passed to template)
    r = client.get(f"/orders/{order_id}")
    assert r.status_code == 200

    # Cleanup receipt file if it was created on disk
    shop_dir = Path(__file__).resolve().parents[1]
    receipt_file = shop_dir / "receipts" / f"receipt_{order_id}.txt"
    if receipt_file.exists():
        receipt_file.unlink()