import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any


TOKEN_SECRET = os.getenv("AUTH_TOKEN_SECRET", "local-development-only-secret").encode()
PASSWORD_ITERATIONS = 310_000


def hash_password(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    password_salt = salt or secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        password_salt,
        PASSWORD_ITERATIONS,
    )
    return password_salt, password_hash


def verify_password(password: str, salt: bytes, expected_hash: bytes) -> bool:
    _, password_hash = hash_password(password, salt)
    return hmac.compare_digest(password_hash, expected_hash)


def issue_access_token(user_id: int, role: str) -> str:
    payload = {"sub": user_id, "role": role, "iat": int(time.time())}
    encoded_payload = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).rstrip(b"=")
    signature = hmac.new(TOKEN_SECRET, encoded_payload, hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=")
    return f"{encoded_payload.decode()}.{encoded_signature.decode()}"


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        encoded_payload, encoded_signature = token.split(".", maxsplit=1)
        expected_signature = hmac.new(
            TOKEN_SECRET, encoded_payload.encode(), hashlib.sha256
        ).digest()
        actual_signature = base64.urlsafe_b64decode(
            encoded_signature + "=" * (-len(encoded_signature) % 4)
        )
        if not hmac.compare_digest(actual_signature, expected_signature):
            return None

        payload = base64.urlsafe_b64decode(
            encoded_payload + "=" * (-len(encoded_payload) % 4)
        )
        decoded = json.loads(payload)
        if not isinstance(decoded, dict) or not isinstance(decoded.get("sub"), int):
            return None
        return decoded
    except (ValueError, TypeError, binascii.Error, json.JSONDecodeError):
        return None
