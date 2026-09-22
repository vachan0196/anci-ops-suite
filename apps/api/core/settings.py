from email.headerregistry import Address
import ipaddress
import re
import socket
from typing import Any, ClassVar, Self
from urllib.parse import SplitResult, urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from apps.api.core.totp_key import validate_totp_key


def _secure_dns_url(value: str) -> tuple[SplitResult, str, int | None] | None:
    """Check shared URL rules without DNS resolution or parser-detail disclosure."""
    if any(c.isspace() or ord(c) < 0x20 or ord(c) == 0x7F for c in value):
        return None
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme != "https" or not parsed.hostname or "://" not in value:
        return None
    authority = value.split("://", 1)[1].split("/", 1)[0]
    if "?" in value or "#" in value or "@" in authority or authority.endswith(":"):
        return None
    if port is not None and not 1 <= port <= 65535:
        return None
    host = parsed.hostname.rstrip(".")
    if not 1 <= len(host) <= 253:
        return None
    if any(
        not 1 <= len(label) <= 63
        or re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label) is None
        for label in host.split(".")
    ):
        return None
    if host == "localhost" or host.endswith(".localhost"):
        return None
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return None
    try:
        socket.inet_aton(host)
    except OSError:
        pass
    else:
        return None
    return parsed, host, port


def _canonical_https_origin(value: str) -> bool:
    checked = _secure_dns_url(value)
    if checked is None:
        return False
    parsed, host, port = checked
    origin = "https://" + host
    if port is not None and port != 443:
        origin += ":" + str(port)
    return parsed.path == "" and value == origin


class Settings(BaseSettings):
    ENV_VALUES: ClassVar[tuple[str, ...]] = (
        "local", "development", "test", "staging", "production"
    )
    EMAIL_BACKEND_ENVIRONMENTS: ClassVar[dict[str, frozenset[str]]] = {
        "local_log": frozenset({"local", "development", "test"}),
        "test_capture": frozenset({"local", "development", "test"}),
        "local_smtp": frozenset({"local", "development"}),
        # Append last to preserve the unknown-backend message prefix asserted by existing tests.
        "resend": frozenset({"staging", "production"}),
    }

    APP_NAME: str = "Anci Ops Suite API"
    ENV: str
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"
    JWT_SECRET_KEY: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    BCRYPT_TEST_FAST: bool = False
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    AUTH_REFRESH_COOKIE_NAME: str = "forecourt_refresh_token"
    APP_BASE_URL: str = "http://localhost:3000"
    EMAIL_BACKEND: str = "local_log"
    EMAIL_FROM_ADDRESS: str | None = None
    EMAIL_FROM_NAME: str = "ForecourtOS"
    SMTP_HOST: str | None = None
    SMTP_PORT: int = Field(default=1025, gt=0, le=65535)
    SMTP_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0, allow_inf_nan=False)
    RESEND_API_KEY: str | None = None
    TOTP_ENCRYPTION_KEY: str | None = None
    CORS_ORIGINS: list[str] = []
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN: str = "20/minute"
    RATE_LIMIT_PASSWORD_RESET_REQUEST: str = "10/hour"
    RATE_LIMIT_PASSWORD_RESET_CONFIRM: str = "10/hour"
    RATE_LIMIT_EMAIL_VERIFICATION_REQUEST: str = "10/hour"
    RATE_LIMIT_EMAIL_VERIFICATION_CONFIRM: str = "10/hour"
    RATE_LIMIT_2FA_VERIFY: str = "5/minute"
    RATE_LIMIT_2FA_STEP_UP: str = "5/minute"
    RATE_LIMIT_2FA_DISABLE: str = "5/minute"
    RATE_LIMIT_2FA_RECOVERY_REGEN: str = "5/minute"
    TWO_FACTOR_STEP_UP_TTL_MINUTES: int = 5
    RATE_LIMIT_DEMAND_INPUT_CREATE: str = "50/minute"
    SENTRY_DSN: str | None = None
    SENTRY_ENVIRONMENT: str | None = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0
    SHIFT_CHANGE_MIN_HOURS: int = 48

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", hide_input_in_errors=True
    )

    @model_validator(mode="before")
    @classmethod
    def require_environment(cls, values: Any) -> Any:
        if isinstance(values, dict) and "ENV" not in values:
            raise ValueError(
                "Missing ENV: received <unset>; permitted values: "
                + ", ".join(cls.ENV_VALUES)
            )
        return values

    @field_validator("ENV", mode="before")
    @classmethod
    def validate_environment(cls, value: Any) -> str:
        if not isinstance(value, str) or value not in cls.ENV_VALUES:
            raise ValueError(
                f"Unknown ENV: received {value!r}; permitted values: "
                + ", ".join(cls.ENV_VALUES)
            )
        return value

    @field_validator("EMAIL_BACKEND", mode="before")
    @classmethod
    def validate_email_backend(cls, value: Any) -> str:
        if not isinstance(value, str) or value not in cls.EMAIL_BACKEND_ENVIRONMENTS:
            raise ValueError(
                f"Unknown EMAIL_BACKEND: received {value!r}; permitted values: "
                + ", ".join(cls.EMAIL_BACKEND_ENVIRONMENTS)
            )
        return value

    @model_validator(mode="after")
    def validate_email_backend_environment(self) -> Self:
        if self.ENV not in self.EMAIL_BACKEND_ENVIRONMENTS[self.EMAIL_BACKEND]:
            permitted = ", ".join(
                backend
                for backend, environments in self.EMAIL_BACKEND_ENVIRONMENTS.items()
                if self.ENV in environments
            ) or "<none implemented>"
            raise ValueError(
                f"Incompatible EMAIL_BACKEND for recognised ENV {self.ENV!r}: "
                f"received {self.EMAIL_BACKEND!r}; permitted values: {permitted}"
            )
        return self

    @model_validator(mode="after")
    def validate_local_smtp_configuration(self) -> Self:
        if self.EMAIL_BACKEND != "local_smtp":
            return self
        if not self.SMTP_HOST or not self.SMTP_HOST.strip():
            raise ValueError("SMTP_HOST is required for EMAIL_BACKEND 'local_smtp'")
        if not self.EMAIL_FROM_ADDRESS or not self.EMAIL_FROM_ADDRESS.strip():
            raise ValueError("EMAIL_FROM_ADDRESS is required for EMAIL_BACKEND 'local_smtp'")
        try:
            sender = Address(display_name=self.EMAIL_FROM_NAME, addr_spec=self.EMAIL_FROM_ADDRESS)
            if not sender.username or not sender.domain:
                raise ValueError
        except ValueError:
            raise ValueError("Invalid EMAIL_FROM_ADDRESS or EMAIL_FROM_NAME for 'local_smtp'") from None
        return self

    @model_validator(mode="after")
    def validate_security_configuration(self) -> Self:
        failures = []
        if not isinstance(self.LOG_LEVEL, str) or self.LOG_LEVEL.upper() not in (
            "DEBUG", "INFO", "WARNING", "WARN", "ERROR", "CRITICAL", "FATAL",
        ):
            failures.append("LOG_LEVEL must name DEBUG, INFO, WARNING, WARN, ERROR, CRITICAL or FATAL without whitespace")
        if self.ENV in ("staging", "production"):
            if self.JWT_SECRET_KEY == "dev-secret-change-me" or len(self.JWT_SECRET_KEY) < 32:
                failures.append("JWT_SECRET_KEY must not use the development default and must contain at least 32 characters")
            if self.BCRYPT_TEST_FAST:
                failures.append("BCRYPT_TEST_FAST must be False")
            try:
                validate_totp_key(self.TOTP_ENCRYPTION_KEY, self.JWT_SECRET_KEY)
            except ValueError:
                failures.append("TOTP_ENCRYPTION_KEY must be a non-blank standard base64 value that decodes to exactly 32 bytes and differs from JWT_SECRET_KEY")
            if not self.CORS_ORIGINS or any(not _canonical_https_origin(origin) for origin in self.CORS_ORIGINS):
                failures.append("CORS_ORIGINS must be non-empty canonical HTTPS DNS origins, without wildcards, localhost or IP addresses")
            if not self.RATE_LIMIT_ENABLED:
                failures.append("RATE_LIMIT_ENABLED must be True")
            if self.JWT_ALGORITHM != "HS256":
                failures.append("JWT_ALGORITHM must equal HS256")
            if _secure_dns_url(self.APP_BASE_URL) is None:
                failures.append("APP_BASE_URL must be an HTTPS DNS URL without localhost, IP addresses, userinfo, query, fragment, whitespace or an invalid port")
        if failures:
            raise ValueError("Invalid security configuration: " + "; ".join(failures))
        return self


settings = Settings()
