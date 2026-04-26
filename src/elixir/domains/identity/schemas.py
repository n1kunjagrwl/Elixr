import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")


def _normalize_phone(v: str) -> str:
    v = v.strip().replace(" ", "").replace("-", "")
    if not _E164_RE.match(v):
        raise ValueError("Phone must be in E.164 format (e.g. +919876543210)")
    return v


# ── Requests ──────────────────────────────────────────────────────────

class RequestOTPBody(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _normalize_phone(v)


class VerifyOTPBody(BaseModel):
    phone: str
    otp: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _normalize_phone(v)

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or len(v) != 6:
            raise ValueError("OTP must be a 6-digit number")
        return v


# ── Responses ─────────────────────────────────────────────────────────

class OTPRequestedResponse(BaseModel):
    message: str = "OTP sent"
    expires_in: int  # seconds


class VerifyOTPResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    phone_e164: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
