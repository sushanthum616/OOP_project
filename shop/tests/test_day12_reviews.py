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


def test_non_purchaser_cannot_review(client):
    _register(client)

    products = client.get("/api/products").json()["items"]
    pid = products[0]["id"]

    r = client.post(
        f"/api/products/{pid}/reviews",
        json={"rating": 5, "title": "Nice", "body": "Test"},
    )
    assert r.status_code == 400
    body = r.json()
    # Day 8 wraps API HTTP errors into {"error": {...}}
    assert "error" in body
    assert "verified purchasers" in body["error"]["message"].lower()


def test_verified_purchaser_can_review(client):
    _register(client)

    products = client.get("/api/products").json()["items"]
    pid = products[0]["id"]

    # Add to cart
    client.post(f"/cart/add/{pid}", data={"qty": 1, "next": "/cart"}, follow_redirects=False)

    # Checkout (creates order => verified purchase check passes because order exists and not cancelled)
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
            "save_address": "",
            "label": "",
            "make_default": "",
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    # Now review should succeed
    r = client.post(
        f"/api/products/{pid}/reviews",
        json={"rating": 5, "title": "Great", "body": "Loved it"},
        follow_redirects=False,
    )
    assert r.status_code == 201
    assert "data" in r.json()

    # List reviews
    r = client.get(f"/api/products/{pid}/reviews")
    assert r.status_code == 200
    payload = r.json()
    assert payload["meta"]["review_count"] >= 1
    assert len(payload["items"]) >= 1