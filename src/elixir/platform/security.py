"""
JWT management for the Elixir platform layer.

Platform-level token exceptions are NOT ElixirError subclasses.
The runtime layer translates these to domain exceptions (shared.exceptions)
on the way out, keeping platform/ free of shared/ imports.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt

_ALGORITHM = "HS256"
_ISSUER = "elixir"


# ── Platform-level exceptions (not ElixirError subclasses) ───────────
# Runtime layer translates these to domain exceptions on the way out.

class SecurityError(Exception):
    pass


class TokenExpiredError(SecurityError):
    pass


class TokenInvalidError(SecurityError):
    pass


# ── JWT ───────────────────────────────────────────────────────────────

def create_access_token(
    user_id: str, session_id: str, secret: str, expiry_minutes: int = 15
) -> tuple[str, str]:
    """Returns (encoded_token, jti)."""
    jti = str(uuid4())
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "sid": session_id,
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(minutes=expiry_minutes),
        "iss": _ISSUER,
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM), jti


def create_refresh_token(
    user_id: str, session_id: str, secret: str, expiry_days: int = 7
) -> tuple[str, str]:
    """Returns (encoded_token, jti)."""
    jti = str(uuid4())
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "sid": session_id,
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(days=expiry_days),
        "iss": _ISSUER,
        "typ": "refresh",
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM), jti


def decode_access_token(token: str, secret: str) -> dict:
    """
    Decode and validate an access token.

    Raises:
        TokenExpiredError: if the token has expired.
        TokenInvalidError: if the token is invalid, has wrong issuer,
            or is a refresh token masquerading as an access token.
    """
    try:
        payload = jwt.decode(token, secret, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Access token has expired")
    except jwt.InvalidTokenError as exc:
        raise TokenInvalidError(str(exc))

    if payload.get("iss") != _ISSUER:
        raise TokenInvalidError("Token issuer is invalid")

    if payload.get("typ") == "refresh":
        raise TokenInvalidError("Refresh token cannot be used as access token")

    return payload


def decode_refresh_token(token: str, secret: str) -> dict:
    """
    Decode and validate a refresh token.

    Raises:
        TokenExpiredError: if the token has expired.
        TokenInvalidError: if the token is invalid, has wrong issuer,
            or is not a refresh token.
    """
    try:
        payload = jwt.decode(token, secret, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Refresh token has expired")
    except jwt.InvalidTokenError as exc:
        raise TokenInvalidError(str(exc))

    if payload.get("iss") != _ISSUER:
        raise TokenInvalidError("Token issuer is invalid")

    if payload.get("typ") != "refresh":
        raise TokenInvalidError("Not a refresh token")

    return payload
