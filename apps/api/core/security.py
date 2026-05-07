from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from pydantic import SecretStr

from apps.api.core.errors import ApiError
from apps.api.core.settings import settings

BCRYPT_MAX_PASSWORD_BYTES = 72
BCRYPT_PASSWORD_TOO_LONG_MESSAGE = (
    "Password must be at most 72 bytes (bcrypt limit)."
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password.startswith("$2"):
        raise ValueError("Unsupported password hash format.")
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        return False


def _normalize_password(password: str | bytes | SecretStr) -> str:
    if isinstance(password, SecretStr):
        normalized_password = password.get_secret_value()
    elif isinstance(password, bytes):
        normalized_password = password.decode("utf-8")
    elif isinstance(password, str):
        normalized_password = password
    else:
        raise ValueError("Password must be a string.")
    return normalized_password


def get_password_hash(password: str | bytes | SecretStr) -> str:
    normalized_password = _normalize_password(password)
    if len(normalized_password.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(BCRYPT_PASSWORD_TOO_LONG_MESSAGE)
    return bcrypt.hashpw(
        normalized_password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def create_access_token(subject: str) -> str:
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise ApiError(
            status_code=401,
            code="AUTH_INVALID_TOKEN",
            message="Invalid authentication token",
        ) from exc

    subject = payload.get("sub")
    if not subject:
        raise ApiError(
            status_code=401,
            code="AUTH_INVALID_TOKEN",
            message="Invalid authentication token",
        )
    return subject
