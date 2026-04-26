import os
import base64
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import bcrypt
import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from elixir.shared.exceptions import TokenExpiredError, TokenInvalidError

_ALGORITHM = "HS256"


# ── OTP ──────────────────────────────────────────────────────────────

def generate_otp() -> str:
    return f"{secrets.randbelow(900000) + 100000:06d}"


def hash_otp(otp: str) -> str:
    return bcrypt.hashpw(otp.encode(), bcrypt.gensalt(rounds=10)).decode()


def verify_otp_hash(otp: str, hashed: str) -> bool:
    return bcrypt.checkpw(otp.encode(), hashed.encode())


# ── JWT ───────────────────────────────────────────────────────────────

def create_access_token(user_id: str, session_id: str, secret: str, expiry_minutes: int = 15) -> tuple[str, str]:
    """Returns (encoded_token, jti)."""
    jti = str(uuid4())
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "sid": session_id,
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(minutes=expiry_minutes),
        "iss": "elixir",
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM), jti


def create_refresh_token(user_id: str, session_id: str, secret: str, expiry_days: int = 7) -> tuple[str, str]:
    """Returns (encoded_token, jti)."""
    jti = str(uuid4())
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "sid": session_id,
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(days=expiry_days),
        "iss": "elixir",
        "typ": "refresh",
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM), jti


def decode_access_token(token: str, secret: str) -> dict:
    try:
        return jwt.decode(token, secret, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Access token has expired")
    except jwt.InvalidTokenError as exc:
        raise TokenInvalidError(str(exc))


def decode_refresh_token(token: str, secret: str) -> dict:
    try:
        payload = jwt.decode(token, secret, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Refresh token has expired")
    except jwt.InvalidTokenError as exc:
        raise TokenInvalidError(str(exc))

    if payload.get("typ") != "refresh":
        raise TokenInvalidError("Not a refresh token")
    return payload


# ── Encryption (AES-256-GCM) ─────────────────────────────────────────

def encrypt_sensitive(value: str, key_hex: str) -> str:
    """Encrypt a string with AES-256-GCM. Returns base64(nonce + ciphertext)."""
    key = bytes.fromhex(key_hex)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, value.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt_sensitive(encrypted: str, key_hex: str) -> str:
    """Decrypt an AES-256-GCM encrypted value."""
    key = bytes.fromhex(key_hex)
    data = base64.b64decode(encrypted.encode())
    nonce, ct = data[:12], data[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None).decode()
