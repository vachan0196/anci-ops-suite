import base64
import binascii


TOTP_KEY_BYTES = 32


def validate_totp_key(key_value: str | None, jwt_secret_key: str) -> bytes:
    if key_value is None or not key_value.strip():
        raise ValueError("TOTP_ENCRYPTION_KEY is required for TOTP secret encryption")
    if key_value == jwt_secret_key:
        raise ValueError("TOTP_ENCRYPTION_KEY must not reuse JWT_SECRET_KEY")
    try:
        decoded = base64.b64decode(key_value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("TOTP_ENCRYPTION_KEY must be base64 encoded") from exc
    if len(decoded) != TOTP_KEY_BYTES:
        raise ValueError("TOTP_ENCRYPTION_KEY must decode to exactly 32 bytes")
    return decoded
