"""Password hashing (bcrypt, direct) and JWT helpers (PyJWT, HS256)."""

import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt

from app.core.clock import now_utc
from app.core.config import get_settings

MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_CHARS = 8
ALGORITHM = "HS256"

# Used to burn the same CPU time when the email is unknown (no user enumeration by timing).
_DUMMY_HASH: bytes | None = None


def password_problem(password: str) -> str | None:
    if len(password) < MIN_PASSWORD_CHARS:
        return f"Password must be at least {MIN_PASSWORD_CHARS} characters."
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return f"Password must be at most {MAX_PASSWORD_BYTES} bytes."
    return None


def hash_password(password: str) -> str:
    raw = password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes.")
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=get_settings().BCRYPT_ROUNDS)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    raw = password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(raw, password_hash.encode())
    except ValueError:
        return False


def dummy_verify(password: str) -> None:
    global _DUMMY_HASH
    rounds = get_settings().BCRYPT_ROUNDS
    if _DUMMY_HASH is None or not _DUMMY_HASH.startswith(f"$2b${rounds:02d}$".encode()):
        _DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt(rounds=rounds))
    verify_password(password, _DUMMY_HASH.decode())


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


TokenType = Literal["access", "refresh"]


def create_token(user_id: uuid.UUID, token_type: TokenType) -> tuple[str, datetime]:
    s = get_settings()
    now = now_utc()
    ttl = (
        timedelta(minutes=s.ACCESS_TOKEN_MINUTES)
        if token_type == "access"
        else timedelta(days=s.REFRESH_TOKEN_DAYS)
    )
    exp = now + ttl
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "exp": exp,
        "iat": now,
        "jti": uuid.uuid4().hex,
        "type": token_type,
    }
    return jwt.encode(claims, s.JWT_SECRET, algorithm=ALGORITHM), exp


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any] | None:
    """Return claims, or None for any failure (bad signature, expired, wrong type...)."""
    try:
        claims = jwt.decode(
            token,
            get_settings().JWT_SECRET,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "iat", "sub", "jti"]},
        )
    except jwt.PyJWTError:
        return None
    if claims.get("type") != expected_type:
        return None
    try:
        uuid.UUID(str(claims["sub"]))
    except ValueError:
        return None
    return claims
