"""Contraseñas Argon2 y tokens que nunca se guardan en texto plano."""

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_password_hasher = PasswordHasher()
_dummy_password_hash = _password_hasher.hash(secrets.token_urlsafe(32))


def password_hash(password: str) -> str:
    return _password_hasher.hash(password)


def password_verify(password: str, encoded_hash: str | None) -> bool:
    try:
        verified = _password_hasher.verify(encoded_hash or _dummy_password_hash, password)
    except (VerificationError, InvalidHashError):
        return False
    return bool(encoded_hash) and verified


def digest_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def csrf_token_for_session(session_token: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), ("csrf:v1:" + session_token).encode("utf-8"), hashlib.sha256).hexdigest()


def new_session_token() -> str:
    return secrets.token_urlsafe(32)
