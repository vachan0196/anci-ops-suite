from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Anci Ops Suite API"
    ENV: str = "dev"
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"
    JWT_SECRET_KEY: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: list[str] = []
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN: str = "20/minute"
    RATE_LIMIT_DEMAND_INPUT_CREATE: str = "50/minute"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
