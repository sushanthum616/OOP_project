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


def test_create_and_list_addresses(client):
    _register(client)

    # Create address
    r = client.post(
        "/addresses/new",
        data={
            "label": "Home",
            "recipient_name": "Test User",
            "line1": "123 Test Street",
            "line2": "",
            "city": "Testville",
            "state": "CA",
            "postal_code": "99999",
            "country": "USA",
            "phone": "111-222",
            "make_default": "on",
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    # List page loads
    r = client.get("/addresses")
    assert r.status_code == 200
    assert "Home" in r.text or "Your Addresses" in r.text