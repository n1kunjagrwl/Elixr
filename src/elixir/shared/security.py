import os
import base64
import secrets

import bcrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# ── OTP ──────────────────────────────────────────────────────────────


def generate_otp() -> str:
    return f"{secrets.randbelow(900000) + 100000:06d}"


def hash_otp(otp: str) -> str:
    return bcrypt.hashpw(otp.encode(), bcrypt.gensalt(rounds=10)).decode()


def verify_otp_hash(otp: str, hashed: str) -> bool:
    return bcrypt.checkpw(otp.encode(), hashed.encode())


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
