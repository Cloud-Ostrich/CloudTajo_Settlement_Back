import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from typing import Any

from dotenv import load_dotenv


load_dotenv()

TOKEN_SECRET = os.getenv("AUTH_TOKEN_SECRET", "local-development-only-secret").encode()
PASSWORD_ITERATIONS = 310_000
revoked_jtis: set[str] = set()


def revoke_jti(jti: str) -> None:
    revoked_jtis.add(jti)


def is_jti_revoked(jti: str) -> bool:
    return jti in revoked_jtis


def clear_revoked_jtis() -> None:
    revoked_jtis.clear()


def hash_password(password: str) -> str:
    password_salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        password_salt,
        PASSWORD_ITERATIONS,
    )
    encoded_salt = base64.urlsafe_b64encode(password_salt).decode()
    encoded_hash = base64.urlsafe_b64encode(password_hash).decode()
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${encoded_salt}${encoded_hash}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_text, encoded_salt, encoded_expected_hash = (
            stored_hash.split("$", maxsplit=3)
        )
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(encoded_salt)
        expected_hash = base64.urlsafe_b64decode(encoded_expected_hash)
        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iterations_text),
        )
        return hmac.compare_digest(password_hash, expected_hash)
    except (ValueError, TypeError, binascii.Error):
        return False


def issue_access_token(user_id: int, role: str) -> str:
    payload = {"sub": user_id, "role": role, "iat": int(time.time()), "jti": uuid.uuid4().hex}
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
