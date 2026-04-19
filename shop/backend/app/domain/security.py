from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


def hash_password(password: str, *, iterations: int = 210_000) -> str:
    """
    Returns a string like:
    pbkdf2_sha256$210000$<salt_b64>$<hash_b64>
    """
    if not password:
        raise ValueError("Password cannot be empty")

    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)

    salt_b64 = base64.b64encode(salt).decode("ascii")
    hash_b64 = base64.b64encode(dk).decode("ascii")
    return f"pbkdf2_sha256${iterations}${salt_b64}${hash_b64}"


def verify_password(password: str, stored: str) -> bool:
    try:
        alg, it_str, salt_b64, hash_b64 = stored.split("$", 3)
        if alg != "pbkdf2_sha256":
            return False
        iterations = int(it_str)

        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(hash_b64.encode("ascii"))

        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False