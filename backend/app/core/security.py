"""Password hashing + JWT helpers for the auth/multi-tenancy stack (issue #123).

We deliberately avoid pulling in bcrypt so the backend stays installable on
minimal environments. Password hashes use PBKDF2-HMAC-SHA256 with a random
salt; the stored format is ``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>``.

JWTs use HS256 with a secret pulled from the ``JWT_SECRET`` environment
variable. If the variable is unset we generate a per-process random secret
— fine for dev, but a deployment should always set a stable value so tokens
survive restarts.
"""

import hashlib
import hmac
import os
import secrets
import time
from typing import Any, Dict, Optional

import jwt

PBKDF2_ITERATIONS = 120_000
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_SECONDS = 60 * 60 * 24 * 7  # 7 days


def _jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        # Cache a fallback across calls within the same process.
        secret = os.environ.setdefault("JWT_SECRET", secrets.token_hex(32))
    return secret


# ── Passwords ───────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations_str, salt_hex, hash_hex = stored.split("$", 3)
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    try:
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(digest, expected)


# ── JWT ────────────────────────────────────────────────────────────────


def create_access_token(
    *,
    user_id: int,
    email: str,
    role: str,
    expires_in: int = JWT_EXPIRES_SECONDS,
) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + expires_in,
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
