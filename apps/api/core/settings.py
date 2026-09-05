from typing import Any, ClassVar, Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENV_VALUES: ClassVar[tuple[str, ...]] = (
        "local", "development", "test", "staging", "production"
    )
    EMAIL_BACKEND_ENVIRONMENTS: ClassVar[dict[str, frozenset[str]]] = {
        "local_log": frozenset({"local", "development", "test"}),
        "test_capture": frozenset({"local", "development", "test"}),
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


settings = Settings()
