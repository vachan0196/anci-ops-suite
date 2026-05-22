import base64
import binascii
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from apps.api.core.settings import settings

TOTP_SECRET_KEY_VERSION = 1
TOTP_NONCE_BYTES = 12
TOTP_KEY_BYTES = 32


@dataclass(frozen=True)
class EncryptedTOTPSecret:
    ciphertext: str
    nonce: str
    key_version: int = TOTP_SECRET_KEY_VERSION


def decode_totp_encryption_key(key_value: str | None = None) -> bytes:
    raw_value = settings.TOTP_ENCRYPTION_KEY if key_value is None else key_value
    if raw_value is None or not raw_value.strip():
        raise ValueError("TOTP_ENCRYPTION_KEY is required for TOTP secret encryption")
    if raw_value == settings.JWT_SECRET_KEY:
        raise ValueError("TOTP_ENCRYPTION_KEY must not reuse JWT_SECRET_KEY")
    try:
        decoded = base64.b64decode(raw_value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("TOTP_ENCRYPTION_KEY must be base64 encoded") from exc
    if len(decoded) != TOTP_KEY_BYTES:
        raise ValueError("TOTP_ENCRYPTION_KEY must decode to exactly 32 bytes")
    return decoded


def encrypt_totp_secret(secret: str, *, key_value: str | None = None) -> EncryptedTOTPSecret:
    key = decode_totp_encryption_key(key_value)
    nonce = os.urandom(TOTP_NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, secret.encode("utf-8"), None)
    return EncryptedTOTPSecret(
        ciphertext=base64.b64encode(ciphertext).decode("ascii"),
        nonce=base64.b64encode(nonce).decode("ascii"),
    )


def decrypt_totp_secret(
    *,
    ciphertext: str,
    nonce: str,
    key_version: int | None,
    key_value: str | None = None,
) -> str:
    if key_version != TOTP_SECRET_KEY_VERSION:
        raise ValueError("Unsupported TOTP secret key version")
    key = decode_totp_encryption_key(key_value)
    try:
        plaintext = AESGCM(key).decrypt(
            base64.b64decode(nonce, validate=True),
            base64.b64decode(ciphertext, validate=True),
            None,
        )
    except (binascii.Error, InvalidTag, ValueError) as exc:
        raise ValueError("Unable to decrypt TOTP secret") from exc
    return plaintext.decode("utf-8")
