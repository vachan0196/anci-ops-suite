from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Anci Ops Suite API"
    ENV: str = "dev"
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"
    JWT_SECRET_KEY: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
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
    RATE_LIMIT_DEMAND_INPUT_CREATE: str = "50/minute"
    SENTRY_DSN: str | None = None
    SENTRY_ENVIRONMENT: str | None = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0
    SHIFT_CHANGE_MIN_HOURS: int = 48

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
